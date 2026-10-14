# Dockerfile - AI Trading Bot
FROM python:3.12-slim

# Metadati immagine
LABEL maintainer="Zoo <trading@example.com>"
LABEL description="AI Trading Bot con Google Gemini Pro e Interactive Brokers"
LABEL version="0.1.0"

# Evita generazione di file .pyc e abilita output non bufferizzato
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

# Crea utente non privilegiato
RUN groupadd -g 1000 trader && \
    useradd -u 1000 -g trader -m -s /bin/bash trader

# Directory di lavoro
WORKDIR /app

# Copia i requisiti e installa le dipendenze
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Crea directory dati e log con permessi corretti
RUN mkdir -p /app/data /app/logs /app/config && \
    chown -R trader:trader /app

# Copia il codice sorgente
COPY --chown=trader:trader app/ /app/app/
COPY --chown=trader:trader core/ /app/core/
COPY --chown=trader:trader data/ /app/data/
COPY --chown=trader:trader strategy/ /app/strategy/
COPY --chown=trader:trader integration/ /app/integration/
COPY --chown=trader:trader utils/ /app/utils/
COPY --chown=trader:trader config/ /app/config/

# Passa all'utente non-root
USER trader

# Espone la porta FastAPI
EXPOSE 8080

# Health check integrato
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Comando di default: avvio server uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
