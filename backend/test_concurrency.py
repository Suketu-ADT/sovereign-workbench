"""
Concurrency stress test for audit hash chain.
Verifies that concurrent requests do not produce race conditions, duplicate indices, or chain forks.
"""

import asyncio
import httpx

BASE_URL = "http://127.0.0.1:8000"
PASSWORD = "changeme123"

async def run_stress_test(run_number: int):
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        # 1. Login as all three operators
        login_suketu = await client.post("/auth/login", json={"email": "suketu.2005@gmail.com", "password": PASSWORD})
        login_morrison = await client.post("/auth/login", json={"email": "j.morrison@plant.internal", "password": PASSWORD})
        login_elena = await client.post("/auth/login", json={"email": "elena.vance@plant.internal", "password": PASSWORD})

        token_s = login_suketu.json()["access_token"]
        token_m = login_morrison.json()["access_token"]
        token_e = login_elena.json()["access_token"]

        headers_s = {"Authorization": f"Bearer {token_s}"}
        headers_m = {"Authorization": f"Bearer {token_m}"}
        headers_e = {"Authorization": f"Bearer {token_e}"}

        # 2. Prepare 24 concurrent query requests
        tasks = []
        queries = [
            (headers_m, "Inspect boiler-102 line A"),
            (headers_m, "Inspect boiler-102 line B"),
            (headers_m, "Inspect turbine-gen-4 vibration"), # RBAC block (requires L2)
            (headers_m, "Inspect reactor-core-aux cooling"), # RBAC block (requires L3)
            (headers_e, "Check turbine-gen-4 bearings"),
            (headers_e, "Check compressor pressure"),
            (headers_e, "Inspect reactor-core-aux valves"), # RBAC block (requires L3)
            (headers_s, "Full audit reactor-core-aux"),
        ]

        # 3 sets of 8 = 24 concurrent requests
        for i in range(24):
            headers, text = queries[i % len(queries)]
            tasks.append(
                client.post("/query", json={"text": f"{text} (seq {i}, run {run_number})", "has_image": False}, headers=headers)
            )

        print(f"--- Run {run_number}: Firing {len(tasks)} concurrent /query requests ---")
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        status_codes = [r.status_code if isinstance(r, httpx.Response) else str(r) for r in responses]
        print(f"Responses: 200s={status_codes.count(200)}, 403s={status_codes.count(403)}, 429s={status_codes.count(429)}")

        # 3. Verify audit chain
        verify_res = await client.get("/audit/verify", headers=headers_s)
        assert verify_res.status_code == 200, f"Verify failed: {verify_res.status_code}"
        verify_data = verify_res.json()
        print(f"Audit verify result: valid={verify_data.get('valid')}, entries_checked={verify_data.get('entries_checked')}, broken_at={verify_data.get('broken_at_index')}")
        assert verify_data["valid"] is True, f"Audit chain broken at index {verify_data.get('broken_at_index')}!"
        assert verify_data["broken_at_index"] is None

        # 4. Fetch up to 200 entries and verify no duplicate idx
        list_res = await client.get("/audit?limit=200", headers=headers_s)
        assert list_res.status_code == 200
        entries = list_res.json()["entries"]
        indices = [e.get("index") if "index" in e else e["idx"] for e in entries]
        print(f"Total entries retrieved: {len(entries)}, unique indices: {len(set(indices))}")
        assert len(indices) == len(set(indices)), f"DUPLICATE INDICES FOUND: {sorted(indices)}"
        print(f"Run {run_number} PASSED with 0 duplicate indices and 100% valid hash chain!\n")

async def main():
    print("Starting back-to-back concurrency verification...")
    for run in range(1, 4):
        await run_stress_test(run)
    print("ALL 3 CONCURRENT STRESS RUNS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(main())
