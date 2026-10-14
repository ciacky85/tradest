# Guida Deploy Stack Portainer - Tradest AI Trading Bot

## 🚀 Panoramica dello Stack

- **Applicazione:** Tradest (AI Trading Bot per XAUUSD con Google Gemini & Interactive Brokers)
- **Repository GitHub:** [`https://github.com/ciacky85/tradest`](https://github.com/ciacky85/tradest)
- **Porta Host Esposta:** `18881` (mappata su porta container `8080`)
- **Cartella Configurazioni Esterne (Host):** `/srv/docker_conf/configs/tradest_conf`

---

## 📁 Struttura Directory sull'Host

Prima del primo deploy, assicurarsi che la cartella esista sull'host:

```bash
mkdir -p /srv/docker_conf/configs/tradest_conf/config
mkdir -p /srv/docker_conf/configs/tradest_conf/data
mkdir -p /srv/docker_conf/configs/tradest_conf/logs
chmod -R 775 /srv/docker_conf/configs/tradest_conf
```

---

## 🛠️ Configurazione Stack Portainer (Web UI)

1. Accedere al pannello **Portainer**
2. Selezionare l'ambiente Docker e andare su **Stacks** → **Add Stack**
3. Nome Stack: `tradest`
4. Metodo di build: **Repository** oppure **Web editor**
   - **Repository URL:** `https://github.com/ciacky85/tradest.git`
   - **Repository reference:** `refs/heads/main`
   - **Compose path:** `docker/docker-compose.portainer.yml`
5. In alternativa incollare il seguente contenuto nel **Web editor**:

```yaml
version: '3.8'

services:
  tradest:
    image: tradest:latest
    build:
      context: https://github.com/ciacky85/tradest.git#main
      dockerfile: docker/Dockerfile
    container_name: tradest
    restart: unless-stopped
    ports:
      - "18881:8080"
    environment:
      - APP_NAME=Tradest-AI-Bot
      - APP_ENV=production
      - APP_DEBUG=false
      - APP_HOST=0.0.0.0
      - APP_PORT=8080
      - APP_LOG_LEVEL=INFO
      - IBKR_HOST=192.168.1.212
      - IBKR_PORT=4004
      - IBKR_CLIENT_ID=500
      - NOTIFY_WEBHOOK_URL=http://192.168.1.212:9008/notify
      - NOTIFY_ENABLED=true
      - TRADING_ENABLED=false
      - TRADING_MODE=paper
      - MAX_DAILY_LOSS=500.0
      - EMERGENCY_STOP_LOSS=1000.0
      - AI_MIN_CONFIDENCE=0.70
      - TIMEZONE=Europe/Rome
      - TZ=Europe/Rome
    volumes:
      - /srv/docker_conf/configs/tradest_conf/config:/app/config:z
      - /srv/docker_conf/configs/tradest_conf/data:/app/data:z
      - /srv/docker_conf/configs/tradest_conf/logs:/app/logs:z
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 15s
    networks:
      - tradest-network

networks:
  tradest-network:
    driver: bridge
```

6. Cliccare **Deploy the stack**.

---

## 🌐 Accesso e Configurazione WebApp

- **URL Dashboard:** `http://<IP-HOST>:18881/`
- **Documentazione Swagger API:** `http://<IP-HOST>:18881/docs`

Dalla dashboard è possibile:
1. Inserire la Google Gemini API Key
2. Recuperare i modelli disponibili dall'account Google via pulsante *Aggiorna Modelli da Google*
3. Selezionare il modello desiderato (es: `gemini-1.5-pro`, `gemini-1.5-flash`, `gemini-2.0-flash-exp`)
4. Eseguire test di connessione in tempo reale e simulare analisi di trade su XAUUSD
