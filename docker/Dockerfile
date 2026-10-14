# Dockerfile - Tradest AI Trading Bot
FROM python:3.12-slim

# Metadati immagine
LABEL maintainer="Zoo <ciacky85@users.noreply.github.com>"
LABEL description="Tradest AI Trading Bot con Google Gemini e Interactive Brokers"
LABEL version="0.1.0"

# Evita generazione file .pyc e abilita output non bufferizzato
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    TZ=Europe/Rome

# Installa pacchetti di sistema necessari
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# Directory di lavoro
WORKDIR /app

# Copia i requisiti e installa le dipendenze
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copia il codice sorgente completo nel container
COPY app/ /app/app/
COPY core/ /app/core/
COPY data/ /app/data/
COPY strategy/ /app/strategy/
COPY integration/ /app/integration/
COPY utils/ /app/utils/
COPY config/ /app/config/

# Crea directory dati locali interne di fallback
RUN mkdir -p /app/data /app/logs /tradest_conf

# Copia e imposta lo script di entrypoint
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Espone la porta HTTP
EXPOSE 8080

# Health check integrato
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Entrypoint che prepara l'ambiente e avvia uvicorn
ENTRYPOINT ["/entrypoint.sh"]
