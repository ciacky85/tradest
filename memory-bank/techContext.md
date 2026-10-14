# techContext.md - Tradest AI Trading Bot

## Credenziali e Servizi Esterni (Memorizzate per Tutti i Progetti)

### 1. GitHub
- **Account:** `ciacky85`
- **Personal Access Token:** Salvato nel remote git locale e nelle configurazioni utente protette
- **Repository Tradest:** `https://github.com/ciacky85/tradest.git`

### 2. Infrastruttura Server e Portainer
- **Porta Esposta Tradest:** `18881` (container: `8080`)
- **Cartella Configurazioni Esterne Host:** `/srv/docker_conf/configs/tradest_conf`
  - `/srv/docker_conf/configs/tradest_conf/config` -> `/app/config`
  - `/srv/docker_conf/configs/tradest_conf/data` -> `/app/data`
  - `/srv/docker_conf/configs/tradest_conf/logs` -> `/app/logs`
- **Portainer Compose:** `docker/docker-compose.portainer.yml`

### 3. Google Gemini AI
- **Fornitore:** Google AI Studio (Generative Language API)
- **Discovery Endpoint:** `https://generativelanguage.googleapis.com/v1beta/models`
- **Modelli Supportati:** `gemini-1.5-pro`, `gemini-1.5-flash`, `gemini-2.0-flash-exp` (selezionabili da Web UI)
- **Formato Risposte:** JSON strutturato (`application/json`) con validazione schema Pydantic

### 4. Interactive Brokers (IBKR)
- **Host Gateway:** `192.168.1.212`
- **Porta Gateway:** `4004`
- **Client ID Tradest:** `500`

### 5. Webhook Notifiche (tradeBotNotify)
- **URL:** `http://192.168.1.212:9008/notify`
