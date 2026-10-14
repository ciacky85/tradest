# techContext.md - Tradest AI Trading Bot

## Stack Tecnologico e Indipendenza

Tradest è un'applicazione Python 3.12 moderna e indipendente:
- **Framework Web & API:** FastAPI + Uvicorn
- **AI Engine:** Google Gemini (Generative Language API v1beta / `google-generativeai`)
- **Database:** SQLite asincrono via `aiosqlite`
- **Broker Connectivity:** Connessione diretta Interactive Brokers tramite `ib_insync` (porta 4004, Client ID 500)
- **Frontend Dashboard:** HTML5 + Tailwind CSS (via CDN) con gestione a componenti leggeri

## Stack Portainer e Server
- **Porta Host:** `18881` (mappata su `8080`)
- **Cartella Configurazioni Esterne Host:** `/srv/docker_conf/configs/tradest_conf`
  - Contiene: `trading_params.json`, `symbols.json`, `ai_prompts.json`, `trading.db` e directory `logs/`.
  - Nessun volume sovrascrive i pacchetti sorgente Python (`/app/*`).

## Credenziali e Servizi Esterni Memorizzati
- **GitHub Account:** `ciacky85`
- **Token GitHub:** Memorizzato in `/home/vvelectron/.github_token`
- **Repository Remoto:** `https://github.com/ciacky85/tradest.git`
- **Interactive Brokers Gateway:** `192.168.1.212:4004` (Client ID 500)
- **Webhook Notifiche:** `http://192.168.1.212:9008/notify`
