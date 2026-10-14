# activeContext.md - Tradest AI Trading Bot

## Stato Attuale
- **Versione Corrente:** `1.0.4`
- **Data:** 2026-10-14
- **Repository GitHub:** [`https://github.com/ciacky85/tradest`](https://github.com/ciacky85/tradest)
- **Account GitHub:** `ciacky85`
- **Token GitHub:** Memorizzato in `/home/vvelectron/.github_token`
- **IBKR Gateway:** `192.168.1.212:4004` (VNC: `5900`, Client ID 500, Account verificato: `DUR222070`)
- **Portainer Stack:** Porta `18881` esposta, volume esterno `/srv/docker_conf/configs/tradest_conf`
- **Web Dashboard:** Dashboard Web attiva su `/` con autenticazione Google Gemini, selezione dinamica del modello e test live scelte di trading

## Note Operative
1. **Versione 1.0.4:** Implementata gestione completa credenziali IBKR (username/password) e modalità Paper/Live trading. Aggiunto client [`ibkr_client.py`](../integration/ibkr_client.py:1) con connessione asincrona a Gateway/TWS, estrazione portfolio e posizioni. Migliorata gestione errori 429 quota Gemini con messaggi dettagliati e fallback modelli. Dashboard estesa con sezione configurazione IBKR, test connessione e visualizzazione dati portafoglio.
2. Versione 1.0.3: Risolto l'errore di Portainer "compose pull operation failed: denied". Configurato `pull_policy: build` e aggiunto workflow GitHub Actions in `.github/workflows/docker-publish.yml` per build/pubblicazione su GHCR.
2. In Portainer, disattivare il toggle "Re-pull image" se si esegue il build dal repository Git.
3. Host di Interactive Brokers Gateway impostato su `172.24.0.2:4004`.
4. Il volume esterno host `/srv/docker_conf/configs/tradest_conf` è montato in `/tradest_conf`, isolando il codice Python sorgente ed evitando sovrascritture di moduli.
5. Ad ogni modifica completata: incrementare il numero di versione, riportarlo nei file `.md`, eseguire il commit/push su Git e segnalare la versione all'utente.
