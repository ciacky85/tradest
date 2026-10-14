# Guida Deploy Stack Portainer - Tradest AI Trading Bot

**Versione:** 1.0.3  
**Data:** 2026-10-14  

## 🚀 Panoramica dello Stack

- **Applicazione:** Tradest (Software di Trading Automatico Indipendente basato su Google Gemini AI)
- **Versione Corrente:** `1.0.3`
- **Repository GitHub:** [`https://github.com/ciacky85/tradest`](https://github.com/ciacky85/tradest)
- **Porta Host Esposta:** `18881` (mappata su porta container `8080`)
- **Cartella Configurazioni Esterne Host:** `/srv/docker_conf/configs/tradest_conf`
- **IBKR Gateway:** `172.24.0.2:4004` (VNC: `5900`)
- **Fix Errore Registry Pull:** Nel compose è specificato `pull_policy: build`, dicendo a Docker di compilare direttamente dal sorgente Git senza richiedere autenticazioni a registri esterni.

---

## 📁 Preparazione Directory sull'Host

Prima del primo avvio, assicurati che la cartella esista sull'host:

```bash
mkdir -p /srv/docker_conf/configs/tradest_conf
chmod -R 775 /srv/docker_conf/configs/tradest_conf
```

---

## 🛠️ Configurazione Stack Portainer (Web UI)

1. Accedere al pannello **Portainer**
2. Selezionare l'ambiente Docker locale e andare su **Stacks** → **Add Stack** (o aggiornare lo stack esistente)
3. Nome Stack: `tradest`
4. Selezionare **Repository**:
   - **Repository URL:** `https://github.com/ciacky85/tradest.git`
   - **Repository reference:** `refs/heads/main`
   - **Compose path:** `docker/docker-compose.portainer.yml`
5. **Opzioni di Deploy in Portainer:**
   - **Disattivare** il toggle *"Re-pull image"* (poiché l'immagine viene compilata via build da Git e non pullata da un registry remoto)
   - Cliccare su **Deploy the stack** (o **Update the stack**)

6. In alternativa, tramite **Web editor**, incollare il seguente YAML:

```yaml
version: '3.8'

services:
  tradest:
    build:
      context: https://github.com/ciacky85/tradest.git#main
      dockerfile: docker/Dockerfile
    image: tradest:1.0.3
    pull_policy: build
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
      - TRADEST_CONF_DIR=/tradest_conf
      - IBKR_HOST=172.24.0.2
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
      - /srv/docker_conf/configs/tradest_conf:/tradest_conf:z
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
