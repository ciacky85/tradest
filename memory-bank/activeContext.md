# activeContext.md - Tradest AI Trading Bot

## Stato Attuale
- **Versione Corrente:** `1.0.1`
- **Data:** 2026-10-14
- **Repository GitHub:** [`https://github.com/ciacky85/tradest`](https://github.com/ciacky85/tradest)
- **Account GitHub:** `ciacky85`
- **Token GitHub:** Memorizzato in `/home/vvelectron/.github_token`
- **Portainer Stack:** Porta `18881` esposta, volume esterno `/srv/docker_conf/configs/tradest_conf`
- **Web Dashboard:** Dashboard Web attiva su `/` con autenticazione Google Gemini, selezione dinamica del modello e test live scelte di trading

## Note Architetturali (Regole Operative)
1. Tradest è un'applicazione 100% autonoma ed indipendente, non collegata a Nautilus.
2. Le scelte operative short/long sono guidate live da Google Gemini con selezione dinamica del modello.
3. Il volume esterno host `/srv/docker_conf/configs/tradest_conf` è montato in `/tradest_conf`, isolando il codice Python sorgente ed evitando sovrascritture di moduli.
4. Ad ogni modifica completata: incrementare il numero di versione, riportarlo nei file `.md`, eseguire il commit/push su Git e segnalare la versione all'utente.
