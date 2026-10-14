# activeContext.md - AI Trading Bot

## Stato Attuale
- **Data:** 2026-10-14
- **Fase Attuale:** Fase 1: Setup Base e Infrastruttura (COMPLETATA)
- **Prossima Fase:** Fase 2: Connessione IBKR e Portfolio Manager

## Lavoro Recente
- Creata la struttura directory completa del progetto tradest: `app/`, `core/`, `data/`, `strategy/`, `integration/`, `utils/`, `config/`, `tests/`, `docker/`, `logs/`.
- Definiti i requirements in [`requirements.txt`](requirements.txt) con dipendenze FastAPI, Pydantic, aiosqlite, structlog, ecc.
- Configurato template ambiente [`..env.example`](.env.example).
- Implementato [`app/config.py`](app/config.py) per la gestione centralizzata delle impostazioni con Pydantic Settings.
- Implementato [`app/models.py`](app/models.py) con tutti i modelli di dati (Pydantic).
- Implementato [`utils/logger.py`](utils/logger.py) per logging strutturato via structlog.
- Implementato [`utils/helpers.py`](utils/helpers.py) con utility di calcolo P&L, stop loss, take profit e formattazione.
- Configurato database SQLite asincrono in [`data/database.py`](data/database.py).
- Definiti i parametri di trading in [`config/trading_params.json`](config/trading_params.json).
- Definiti i prompt AI in [`config/ai_prompts.json`](config/ai_prompts.json).
- Definita la configurazione simboli in [`config/symbols.json`](config/symbols.json).
- Implementato [`app/main.py`](app/main.py) con endpoint FastAPI (/health, /status, /config/*, /trades/daily, /ai/decisions, /bot/*).
- Configurato Docker e Compose in [`docker/Dockerfile`](docker/Dockerfile) e [`docker/docker-compose.yml`](docker/docker-compose.yml).
- Creati test unitari in [`tests/test_basic_setup.py`](tests/test_basic_setup.py) e [`tests/test_api_endpoints.py`](tests/test_api_endpoints.py).

## Prossimi Passi
1. Testare l'applicazione base in container Podman effimero secondo le regole di sicurezza.
2. Iniziare la Fase 2: implementare `data/ibkr_connector.py` e `data/portfolio_manager.py`.
