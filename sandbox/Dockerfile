FROM python:3.13-slim

# Create a non-root user and group
RUN groupadd -r sandboxgroup && useradd -r -g sandboxgroup sandboxuser

WORKDIR /app

# Copy the minimal HTTP server
COPY main.py /app/main.py

# Ensure ownership belongs to root so sandboxuser cannot modify it
RUN chown -R root:root /app && chmod -R 555 /app

# Switch to the non-root user
USER sandboxuser

EXPOSE 8080

CMD ["python", "main.py"]
