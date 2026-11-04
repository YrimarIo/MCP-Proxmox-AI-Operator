# Schlankes Python-Image als Basis
FROM python:3.11-slim

# Arbeitsverzeichnis im Container
WORKDIR /app

# System-Abhängigkeiten (falls nötig)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Requirements kopieren und installieren
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Den restlichen Code kopieren
COPY core/ ./core/
COPY utils/ ./utils/
COPY mcp_server.py .
COPY main.py .

# Standardmäßig den MCP-Server starten
# Wenn du die main.py willst, kannst du das beim 'docker run' überschreiben
CMD ["python", "mcp_server.py"]