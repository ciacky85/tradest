# progress.md - AI Trading Bot

## Versione Corrente
- **v1.7.7** (2026-10-17): Aggiunta colonna `simulated` a `executed_operations` con migrazione automatica e retroclassificazione delle vecchie operazioni `EXECUTED` come simulate; il filtro predefinito ora esclude realmente le operazioni simulate e la UI mostra badge `SIMULATO`.
- **v1.6.1** (2026-10-16): Risolti errori JS su badge IBKR, import asyncio mancanti in simulazione AI con aumento timeout, e connessione asincrona SQLite.

## Stato Avanzamento Fasi

| Fase | Descrizione | Stato | Note |
|------|-------------|-------|------|
| **Fase 0** | Planning e Architettura | ✅ Completata | Piano di progetto e todo list definiti |
| **Fase 1** | Setup Base e Infrastruttura | ✅ Completata | Directory, config, FastAPI, models, SQLite, tests |
| **Fase 2** | Connessione IBKR e Portfolio Manager | ✅ Completata | Client ID 500, host 192.168.1.212:4004, credenziali salvabili, portfolio estratto |
| **Fase 3** | Integrazione Google Gemini Pro | ✅ Completata | Omniroute / Antigravity Gateway su 192.168.1.212:9292/v1 & Google AI Studio REST nativo, zero 429 quota limits |
| **Fase 4** | Market Analyzer e Dati Real-time | ✅ Completata | Barre 30d/7d da IBKR, calcolo matematico RSI, EMA 9/21, MACD, ATR, Bollinger, pivot supporti/resistenze |
| **Fase 5** | Risk Manager e Validazioni | ✅ Completata | Validazione pre-avvio: verifica strategia scalping recente, budget $5000 trade, buying power e portafoglio reale |
| **Fase 6** | Order Executor | 🔲 Non avviata | Esecuzione ordini IBKR con bracket SL/TP |
| **Fase 7** | Integrazione tradeBotNotify | 🔲 Non avviata | Webhook porta 9008 per notifiche Telegram |
| **Fase 8** | Orchestratore e Scheduler | ✅ Completata | MultiBotEngine parallelo per simbolo, cicli background, log SQLite |
| **Fase 9** | Containerizzazione e Deploy | 🔲 Non avviata | Podman container produzione |
| **Fase 10** | Testing e Ottimizzazione | 🔲 Non avviata | Paper trading e validazione completa |

## Checklist Fase 1 (Dettagli)
- [x] Struttura directory creata
- [x] Package `__init__.py` creati
- [x] `requirements.txt` creato
- [x] `.env.example` creato
- [x] `app/config.py` implementato
- [x] `app/models.py` implementato
- [x] `utils/logger.py` implementato
- [x] `utils/helpers.py` implementato
- [x] `config/trading_params.json` creato
- [x] `config/ai_prompts.json` creato
- [x] `config/symbols.json` creato
- [x] `data/database.py` implementato
- [x] `app/main.py` implementato
- [x] `docker/Dockerfile` e `docker/docker-compose.yml` creati
- [x] `tests/test_basic_setup.py` e `tests/test_api_endpoints.py` creati
- [x] Memory Bank inizializzata
