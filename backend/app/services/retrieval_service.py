"""
Sovereign On-Premise Retrieval Service.
Uses Qdrant vector database with FastEmbed (BAAI/bge-small-en-v1.5)
and database-level RBAC pre-filtering (min_clearance <= operator_clearance).
"""

import logging
import os
import uuid
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    PointStruct,
    Range,
    VectorParams,
)

from app.core.config import settings
from app.db.plant_manuals import PLANT_MANUAL_CHUNKS
from app.schemas.query import RetrievedChunk

logger = logging.getLogger(__name__)

# Namespace UUID for deterministic chunk point IDs
_CHUNK_NAMESPACE = uuid.UUID("9a5d3f28-8547-49d7-873b-e3c3bdf6a3e1")


class FallbackDeterministicEmbedder:
    """Fallback 384-dimensional deterministic embedder for zero-network air-gapped fallbacks."""

    def __init__(self, dim: int = 384):
        self.dim = dim

    def embed(self, texts: list[str]):
        import hashlib
        import numpy as np

        for text in texts:
            # Produce deterministic pseudo-embedding based on text tokens
            tokens = text.lower().split()
            vec = np.zeros(self.dim, dtype=np.float32)
            for i, token in enumerate(tokens):
                h = int(hashlib.sha256(token.encode("utf-8")).hexdigest()[:8], 16)
                idx = h % self.dim
                sign = 1.0 if (h >> 4) % 2 == 0 else -1.0
                vec[idx] += sign * (1.0 / (1.0 + i * 0.05))
            norm = np.linalg.norm(vec)
            if norm > 1e-9:
                vec /= norm
            yield vec


class RetrievalService:
    """Manages on-premise vector embeddings and RBAC-filtered retrieval."""

    def __init__(
        self,
        storage_path: str | None = None,
        url: str | None = None,
        collection_name: str | None = None,
        model_name: str | None = None,
    ):
        self.storage_path = storage_path or settings.QDRANT_STORAGE_PATH
        self.url = url or settings.QDRANT_URL
        self.collection_name = collection_name or settings.QDRANT_COLLECTION
        self.model_name = model_name or settings.EMBEDDING_MODEL
        self.client: QdrantClient | None = None
        self.embedder: Any = None
        self._initialized = False

    def _init_embedder(self):
        try:
            from fastembed import TextEmbedding

            logger.info("Initializing FastEmbed with model: %s", self.model_name)
            self.embedder = TextEmbedding(model_name=self.model_name)
        except Exception as e:
            logger.warning(
                "FastEmbed initialization fallback: %s. Using FallbackDeterministicEmbedder.",
                e,
            )
            self.embedder = FallbackDeterministicEmbedder(dim=384)

    def _init_client(self):
        if self.url:
            logger.info("Connecting to remote Qdrant at %s", self.url)
            self.client = QdrantClient(url=self.url)
        elif self.storage_path == ":memory:":
            logger.info("Initializing in-memory Qdrant instance")
            self.client = QdrantClient(":memory:")
        else:
            try:
                os.makedirs(self.storage_path, exist_ok=True)
                logger.info("Initializing embedded Qdrant at %s", self.storage_path)
                self.client = QdrantClient(path=self.storage_path)
            except Exception as e:
                logger.warning(
                    "Could not initialize disk Qdrant at %s (%s). Falling back to :memory:.",
                    self.storage_path,
                    e,
                )
                self.client = QdrantClient(":memory:")

    def initialize(self, force_reseed: bool = False):
        """Initializes client, embedder, collection, and seeds operational manuals."""
        if self._initialized and not force_reseed:
            return

        self._init_embedder()
        self._init_client()

        # Check if collection exists
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)

        if not exists:
            logger.info("Creating Qdrant collection '%s' (384-dim COSINE)", self.collection_name)
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE),
            )
            self.seed_manuals()
        else:
            count = self.client.count(collection_name=self.collection_name).count
            if count == 0 or force_reseed:
                logger.info("Collection '%s' empty or reseed requested; seeding manuals...", self.collection_name)
                self.seed_manuals()

        self._initialized = True

    def seed_manuals(self):
        """Embeds and upserts the operational plant SOPs into Qdrant."""
        logger.info("Seeding %d plant manual chunks into Qdrant...", len(PLANT_MANUAL_CHUNKS))
        texts = [chunk["content"] for chunk in PLANT_MANUAL_CHUNKS]
        embeddings = list(self.embedder.embed(texts))

        points = []
        for chunk, emb in zip(PLANT_MANUAL_CHUNKS, embeddings):
            point_id = str(uuid.uuid5(_CHUNK_NAMESPACE, chunk["id"]))
            vec = emb.tolist() if hasattr(emb, "tolist") else list(emb)
            points.append(
                PointStruct(
                    id=point_id,
                    vector=vec,
                    payload=chunk,
                )
            )

        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
        )
        logger.info("Successfully seeded %d points into '%s'", len(points), self.collection_name)

    def retrieve(
        self,
        query: str,
        operator_clearance: int,
        top_k: int | None = None,
    ) -> list[RetrievedChunk]:
        """
        Performs semantic vector search with strict RBAC pre-filtering:
        Only chunks where min_clearance <= operator_clearance are evaluated.
        """
        if not self._initialized:
            self.initialize()

        k = top_k or settings.RAG_TOP_K

        # 1. Embed query
        query_emb = list(self.embedder.embed([query]))[0]
        query_vector = query_emb.tolist() if hasattr(query_emb, "tolist") else list(query_emb)

        # 2. Construct RBAC pre-filter (min_clearance <= operator_clearance)
        rbac_filter = Filter(
            must=[
                FieldCondition(
                    key="min_clearance",
                    range=Range(lte=operator_clearance),
                )
            ]
        )

        # 3. Query Qdrant with pre-filter applied at vector index
        search_result = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=rbac_filter,
            limit=k,
        )

        retrieved = []
        for point in search_result.points:
            payload = point.payload or {}
            retrieved.append(
                RetrievedChunk(
                    id=str(payload.get("id", point.id)),
                    unit=str(payload.get("unit", "")),
                    sop_id=str(payload.get("sop_id", "")),
                    title=str(payload.get("title", "")),
                    content=str(payload.get("content", "")),
                    min_clearance=int(payload.get("min_clearance", 0)),
                    score=float(point.score if point.score is not None else 0.0),
                )
            )

        return retrieved


# Singleton instance for application lifetime
retrieval_service = RetrievalService()
