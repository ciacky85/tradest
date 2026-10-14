# Guida Deploy Stack Portainer - Tradest AI Trading Bot

## 🚀 Panoramica dello Stack

- **Applicazione:** Tradest (Software di Trading Automatico Indipendente basato su Google Gemini AI)
- **Repository GitHub:** [`https://github.com/ciacky85/tradest`](https://github.com/ciacky85/tradest)
- **Porta Host Esposta:** `18881` (mappata su porta container `8080`)
- **Cartella Configurazioni Esterne Host:** `/srv/docker_conf/configs/tradest_conf`
- **Architettura:** Applicazione autonoma, leggera e indipendente; decisioni di trade short/long prese direttamente in tempo reale da Google Gemini (modello selezionabile via UI tra `gemini-1.5-pro`, `gemini-1.5-flash`, `gemini-2.0-flash-exp`) sulla base dello storico e delle condizioni live del mercato.

---

## 📁 Preparazione Directory sull'Host

Prima del primo avvio, assicurati che la cartella esista sull'host:

```bash
mkdir -p /srv/docker_conf/configs/tradest_conf
chmod -R 775 /srv/docker_conf/configs/tradest_conf
```

> **Nota:** Al primo avvio, il container popola automaticamente la cartella `/srv/docker_conf/configs/tradest_conf` con i file di configurazione iniziali (`trading_params.json`, `ai_prompts.json`, `symbols.json`) e crea il database SQLite persistente `trading.db` e la cartella `logs/`.

---

## 🛠️ Configurazione Stack Portainer (Web UI)

1. Accedere al pannello **Portainer**
2. Selezionare l'ambiente Docker locale e andare su **Stacks** → **Add Stack**
3. Nome Stack: `tradest`
4. Selezionare **Repository**:
   - **Repository URL:** `https://github.com/ciacky85/tradest.git`
   - **Repository reference:** `refs/heads/main`
   - **Compose path:** `docker/docker-compose.portainer.yml`
5. Oppure selezionare **Web editor** e incollare il compose seguente:

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
      - TRADEST_CONF_DIR=/tradest_conf
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
      # Cartella host persistente per configurazioni, DB SQLite e log
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

6. Cliccare su **Deploy the stack**.

---

## 🌐 Dashboard Web & Selezione Modello Gemini

Una volta avviato lo stack, collegarsi con il browser a:
- **Dashboard Web:** `http://<IP-DEL-TUO-SERVER>:18881/`
- **Swagger API Docs:** `http://<IP-DEL-TUO-SERVER>:18881/docs`

Dalla dashboard è possibile:
1. Inserire la Google API Key (ottenibile su Google AI Studio)
2. Cliccare su **Aggiorna Modelli da Google** per scoprire i modelli disponibili sul tuo account
3. Selezionare il modello desiderato (es: `gemini-1.5-pro` per analisi approfondite o `gemini-1.5-flash` per risposte ultrarapide)
4. Cliccare su **Test Connessione Live** per verificare la risposta di Google Gemini
5. Cliccare su **Simula Analisi AI su XAUUSD** per testare la decisione in tempo reale sulle posizioni Long/Short con i relativi livelli di Stop-Loss e Take-Profit
