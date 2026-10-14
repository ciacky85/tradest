# activeContext.md - Tradest AI Trading Bot

## Stato Attuale
- **Versione Corrente:** `1.0.2`
- **Data:** 2026-10-14
- **Repository GitHub:** [`https://github.com/ciacky85/tradest`](https://github.com/ciacky85/tradest)
- **Account GitHub:** `ciacky85`
- **Token GitHub:** Memorizzato in `/home/vvelectron/.github_token`
- **IBKR Gateway:** `172.24.0.2:4004` (VNC: `5900`, Client ID 500)
- **Portainer Stack:** Porta `18881` esposta, volume esterno `/srv/docker_conf/configs/tradest_conf`
- **Web Dashboard:** Dashboard Web attiva su `/` con autenticazione Google Gemini, selezione dinamica del modello e test live scelte di trading

## Note Operative
1. Versione 1.0.2: Rimosso `image:` dal compose di Portainer per prevenire errori di pull da registri protetti, costringendo Portainer a costruire l'immagine direttamente dal contesto Git di `main`.
2. Host di Interactive Brokers Gateway aggiornato a `172.24.0.2:4004`.
3. Il volume esterno host `/srv/docker_conf/configs/tradest_conf` è montato in `/tradest_conf`, isolando il codice Python sorgente ed evitando sovrascritture di moduli.
4. Ad ogni modifica completata: incrementare il numero di versione, riportarlo nei file `.md`, eseguire il commit/push su Git e segnalare la versione all'utente.
