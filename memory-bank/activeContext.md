# activeContext.md - Tradest AI Trading Bot

## Stato Attuale
- **Data:** 2026-10-14
- **Repository GitHub:** [`https://github.com/ciacky85/tradest`](https://github.com/ciacky85/tradest)
- **Account GitHub:** `ciacky85`
- **GitHub Token:** Configurato nel remote git locale e memorizzato per tutti i progetti futuri
- **Portainer Stack:** Porta `18881` esposta, volume esterno `/srv/docker_conf/configs/tradest_conf`
- **Web Dashboard:** Dashboard Web attiva su `/` con autenticazione Google Gemini, selezione dinamica del modello e test live scelte di trading

## Ultimi Aggiornamenti
1. Creata repository remota `ciacky85/tradest` via GitHub REST API.
2. Inizializzato git locale, committato e pushato il codice sorgente del progetto sul branch `main`.
3. Creato lo stack per Portainer in [`docker/docker-compose.portainer.yml`](docker/docker-compose.portainer.yml) con porta `18881:8080` e mapping `/srv/docker_conf/configs/tradest_conf`.
4. Implementata l'interfaccia Web UI in [`app/templates/index.html`](app/templates/index.html) con design Tailwind/Dark Mode.
5. Implementato [`integration/gemini_client.py`](integration/gemini_client.py) per discovery dinamico dei modelli Google Gemini supportati dall'account, selezione a runtime e generazione decisioni JSON.
6. Aggiunti endpoint FastAPI in [`app/main.py`](app/main.py) per:
   - Configurazione API key e modello Gemini (`/api/gemini/config`)
   - Discovery modelli da Google (`/api/gemini/models`)
   - Test rapido connessione (`/api/gemini/test`)
   - Simulazione analisi scelte di trade in tempo reale (`/api/gemini/simulate-trade`)
7. Creati test unitari in [`tests/test_gemini_integration.py`](tests/test_gemini_integration.py) e redatta guida [`PORTAINER.md`](PORTAINER.md).
