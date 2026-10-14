# 🤖 AI Trading Bot - Todo List Implementazione

**Progetto:** AI Trading Bot con Google Gemini Pro  
**Workspace:** `/home/vvelectron/VisualVibe Workdirs/Nautilus/ai-trading-bot/`  
**Data:** 2026-10-13

---

## 📋 Fasi di Implementazione

### ✅ Fase 0: Planning e Architettura
- [x] Analizzare sistema Nautilus esistente
- [x] Definire architettura AI Trading Bot
- [x] Creare piano di progetto dettagliato
- [x] Creare diagrammi Mermaid

---

### ✅ Fase 1: Setup Base e Infrastruttura

- [x] Creare struttura directory nel workspace tradest
- [x] Creare sottodirectory: app/, core/, data/, strategy/, integration/, utils/, config/, tests/, docker/, logs/, memory-bank/
- [x] Creare file `requirements.txt` con tutte le dipendenze
- [x] Creare file `.env.example` con template variabili ambiente
- [x] Creare file `.gitignore` appropriato
- [x] Implementare `app/main.py` con FastAPI base
- [x] Implementare `app/config.py` per gestione configurazioni
- [x] Implementare `app/models.py` con modelli Pydantic
- [x] Implementare `utils/logger.py` per logging strutturato
- [x] Creare `config/trading_params.json` con parametri XAUUSD
- [x] Creare `config/ai_prompts.json` con template prompt
- [x] Creare `config/symbols.json` con configurazione simboli
- [x] Implementare `data/database.py` con schema SQLite
- [x] Testare avvio applicazione base
- [x] Verificare logging funzionante
- [x] Verificare caricamento configurazioni

---

### 🔲 Fase 2: Connessione IBKR e Portfolio Manager

- [ ] Implementare `data/ibkr_connector.py` con Nautilus Trader
- [ ] Configurare connessione a 192.168.1.212:4004
- [ ] Assegnare Client ID 500 (non in conflitto con kernel esistenti)
- [ ] Implementare metodo `connect()` e `disconnect()`
- [ ] Implementare `get_account_summary()`
- [ ] Implementare `get_positions()`
- [ ] Implementare `get_market_data(symbol)`
- [ ] Implementare `place_order()`
- [ ] Implementare `get_order_status()`
- [ ] Implementare `cancel_order()`
- [ ] Implementare `data/portfolio_manager.py`
- [ ] Implementare `sync_portfolio()` da IBKR
- [ ] Implementare calcolo P&L real-time
- [ ] Implementare `get_transaction_history()`
- [ ] Implementare `get_available_cash()`
- [ ] Implementare `get_daily_pnl()`
- [ ] Creare `tests/test_ibkr_connection.py`
- [ ] Testare connessione IBKR con paper trading
- [ ] Verificare lettura posizioni corretta
- [ ] Verificare lettura bilanci corretta

---

### 🔲 Fase 3: Integrazione Google Gemini Pro

- [ ] Ottenere API key Google Gemini Pro (https://ai.google.dev/)
- [ ] Installare SDK `google-generativeai`
- [ ] Implementare `integration/gemini_client.py`
- [ ] Configurare autenticazione API
- [ ] Implementare gestione rate limiting (15 req/min free tier)
- [ ] Implementare retry automatico su errori temporanei
- [ ] Implementare `core/ai_engine.py`
- [ ] Implementare `analyze_market()` con prompt strutturato
- [ ] Implementare `ask_investment_question()`
- [ ] Implementare `get_risk_assessment()`
- [ ] Implementare parsing risposta JSON da Gemini
- [ ] Implementare validazione risposta AI
- [ ] Implementare fallback su errori API
- [ ] Creare template prompt in `config/ai_prompts.json`
- [ ] Ottimizzare prompt per decisioni trading
- [ ] Creare `tests/test_gemini_integration.py`
- [ ] Testare chiamate API con dati mock
- [ ] Verificare parsing risposte corretto
- [ ] Verificare rate limiting funzionante

---

### 🔲 Fase 4: Market Analyzer e Indicatori Tecnici

- [ ] Implementare `strategy/market_analyzer.py`
- [ ] Implementare `get_market_snapshot(symbol)`
- [ ] Implementare raccolta dati real-time da IBKR
- [ ] Implementare calcolo RSI (14 periodi)
- [ ] Implementare calcolo EMA (20, 50 periodi)
- [ ] Implementare calcolo MACD
- [ ] Implementare calcolo ATR (14 periodi)
- [ ] Implementare calcolo Bande di Bollinger
- [ ] Implementare identificazione supporti/resistenze
- [ ] Implementare rilevamento trend orario
- [ ] Implementare calcolo volatilità
- [ ] Implementare `data/market_data_cache.py`
- [ ] Implementare cache in memoria con TTL
- [ ] Implementare invalidazione cache su aggiornamenti
- [ ] Testare calcolo indicatori con dati storici
- [ ] Verificare accuratezza indicatori vs TradingView
- [ ] Verificare performance cache

---

### 🔲 Fase 5: Risk Manager e Validazioni

- [ ] Implementare `strategy/risk_manager.py`
- [ ] Implementare `validate_strategy()`
- [ ] Implementare controllo `max_budget_per_trade`
- [ ] Implementare controllo `trading_mode` (long/short/both)
- [ ] Implementare controllo `max_position_size`
- [ ] Implementare controllo `max_daily_loss`
- [ ] Implementare controllo `min_ai_confidence`
- [ ] Implementare controllo cash disponibile
- [ ] Implementare controllo esposizione totale
- [ ] Implementare verifica stop-loss obbligatorio
- [ ] Implementare `check_position_limits()`
- [ ] Implementare `check_daily_loss_limit()`
- [ ] Implementare `calculate_position_size()`
- [ ] Implementare `should_force_close()`
- [ ] Implementare emergency stop su loss critico
- [ ] Implementare controllo trading hours
- [ ] Creare `tests/test_risk_manager.py`
- [ ] Testare validazione con scenari limite
- [ ] Testare emergency stop con loss simulati
- [ ] Verificare tutti i limiti rispettati

---

### 🔲 Fase 6: Order Executor

- [ ] Implementare `strategy/order_executor.py`
- [ ] Implementare `execute_strategy()`
- [ ] Implementare `place_market_order()`
- [ ] Implementare `place_stop_loss()` automatico
- [ ] Implementare `place_take_profit()` automatico
- [ ] Implementare `monitor_order()` con polling
- [ ] Implementare timeout su ordini non riempiti
- [ ] Implementare `cancel_pending_orders()`
- [ ] Implementare retry logic su errori temporanei
- [ ] Implementare logging dettagliato ogni ordine
- [ ] Implementare gestione errori IBKR (ordine rifiutato, etc)
- [ ] Implementare calcolo commissioni broker
- [ ] Implementare calcolo net profit
- [ ] Testare ordini su paper trading IBKR
- [ ] Verificare stop-loss attivato correttamente
- [ ] Verificare take-profit attivato correttamente
- [ ] Verificare gestione errori robusta

---

### 🔲 Fase 7: Integrazione Notifiche tradeBotNotify

- [ ] Implementare `integration/notification_client.py`
- [ ] Configurare webhook URL (http://192.168.1.212:9008/notify)
- [ ] Implementare `send_trade_notification()`
- [ ] Implementare `send_error_notification()`
- [ ] Implementare `send_daily_summary()`
- [ ] Implementare retry automatico su fallimento webhook
- [ ] Implementare timeout su chiamate HTTP
- [ ] Formattare payload compatibile con tradeBotNotify
- [ ] Aggiungere campo `source: "AI-TradingBot"`
- [ ] Aggiungere campo `strategy_reasoning` con logica AI
- [ ] Testare invio notifica a tradeBotNotify
- [ ] Verificare ricezione su Telegram
- [ ] Verificare formato messaggio corretto
- [ ] Testare retry su fallimenti
- [ ] (Opzionale) Aggiornare tradeBotNotify per nuovi campi

---

### 🔲 Fase 8: Trading Orchestrator e Scheduling

- [ ] Implementare `core/orchestrator.py`
- [ ] Implementare inizializzazione tutti i moduli
- [ ] Implementare `run_trading_cycle(symbol)`
- [ ] Implementare flusso completo: sync → analyze → AI → validate → execute
- [ ] Implementare gestione stato applicazione
- [ ] Implementare shutdown graceful
- [ ] Implementare recovery da crash
- [ ] Implementare `core/scheduler.py` con APScheduler
- [ ] Configurare job XAUUSD ogni 30 secondi
- [ ] Configurare job sync portfolio ogni 5 minuti
- [ ] Configurare job daily summary ogni 24h
- [ ] Implementare gestione timezone (Europe/Rome)
- [ ] Implementare controllo trading hours
- [ ] Implementare pause/resume trading
- [ ] Testare ciclo completo end-to-end con dati mock
- [ ] Testare schedulazione con intervalli reali
- [ ] Verificare gestione errori durante ciclo
- [ ] Verificare recovery da interruzioni

---

### 🔲 Fase 9: Containerizzazione e Deploy

- [ ] Creare `docker/Dockerfile`
- [ ] Configurare base image `python:3.12-slim`
- [ ] Installare dipendenze sistema necessarie
- [ ] Copiare codice applicazione
- [ ] Configurare variabili ambiente
- [ ] Esporre porta 9009 (API/dashboard)
- [ ] Configurare CMD per avvio applicazione
- [ ] Creare `docker/docker-compose.yml`
- [ ] Configurare servizio ai-trading-bot
- [ ] Configurare volumi per persistenza (data/, logs/)
- [ ] Configurare network per comunicazione con tradeBotNotify
- [ ] Configurare variabili ambiente (IBKR, Gemini, etc)
- [ ] Configurare healthcheck
- [ ] Configurare restart policy
- [ ] Testare build immagine con Podman in container effimero
- [ ] Testare avvio container con docker-compose
- [ ] Verificare connessione IBKR da container
- [ ] Verificare comunicazione con tradeBotNotify
- [ ] Verificare persistenza dati dopo restart
- [ ] Creare script `deploy.sh` per automazione
- [ ] Documentare procedura deploy in README

---

### 🔲 Fase 10: Testing e Ottimizzazione

- [ ] Configurare paper trading su IBKR
- [ ] Avviare bot in modalità paper trading
- [ ] Monitorare operazioni per 1 settimana
- [ ] Raccogliere metriche performance (win rate, profit factor, etc)
- [ ] Analizzare decisioni AI (confidenza vs esito)
- [ ] Identificare pattern di successo/fallimento
- [ ] Ottimizzare prompt Gemini per migliori risultati
- [ ] Ottimizzare parametri stop-loss e take-profit
- [ ] Ottimizzare soglia confidenza minima AI
- [ ] Testare gestione errori con disconnessioni simulate
- [ ] Testare gestione errori API Gemini (rate limit, timeout)
- [ ] Testare emergency stop con loss simulati
- [ ] Testare recovery da crash improvviso
- [ ] Testare comportamento in ore non trading
- [ ] Implementare dashboard web per monitoring (opzionale)
- [ ] Creare API endpoint `/health`, `/portfolio`, `/trades`
- [ ] Ottimizzare consumo memoria e CPU
- [ ] Ottimizzare latenza decisioni AI
- [ ] Scrivere documentazione utente in README.md
- [ ] Creare ARCHITECTURE.md con dettagli tecnici

---

### 🔲 Fase 11: Produzione e Monitoring

- [ ] Verificare tutti i test passati
- [ ] Verificare performance paper trading soddisfacenti
- [ ] Configurare account IBKR reale (o sub-account)
- [ ] Configurare capitale iniziale limitato (es: $1000)
- [ ] Deploy su produzione con configurazioni finali
- [ ] Avviare bot in modalità real-money
- [ ] Monitorare prime 10 operazioni real-time
- [ ] Configurare backup automatico database (cron ogni 6h)
- [ ] Configurare alerting avanzato (PagerDuty, email, etc)
- [ ] Creare dashboard Grafana per metriche (opzionale)
- [ ] Implementare logging centralizzato (ELK stack, opzionale)
- [ ] Implementare monitoring costi API Gemini
- [ ] Implementare alert su costi API sopra soglia
- [ ] Creare runbook per incident response
- [ ] Creare piano disaster recovery
- [ ] Documentare procedure manutenzione
- [ ] Schedulare review performance settimanale
- [ ] Implementare A/B testing strategie AI (opzionale)

---

## 🎯 Criteri di Successo per Go-Live

### Requisiti Tecnici
- [ ] Uptime > 99% durante paper trading (1 settimana)
- [ ] Zero crash non gestiti
- [ ] Latenza decisione AI < 3s (media)
- [ ] Latenza esecuzione ordine < 1s (media)
- [ ] Tutti i test automatici passati
- [ ] Documentazione completa

### Requisiti Trading (Paper Trading)
- [ ] Win rate > 50%
- [ ] Profit factor > 1.2
- [ ] Max drawdown < 5%
- [ ] Rispetto di tutti i limiti configurati (0 violazioni)
- [ ] Emergency stop testato e funzionante
- [ ] Notifiche Telegram funzionanti al 100%

### Requisiti Sicurezza
- [ ] API keys in variabili ambiente (non hardcoded)
- [ ] Database backup configurato
- [ ] Stop-loss su tutte le posizioni aperte
- [ ] Emergency stop testato
- [ ] Monitoring attivo

---

## 📊 Metriche da Tracciare

### Durante Sviluppo
- [ ] Coverage test > 80%
- [ ] Numero bug critici: 0
- [ ] Numero warning linter: 0
- [ ] Tempo build immagine Docker
- [ ] Tempo avvio applicazione

### Durante Paper Trading
- [ ] Numero trade al giorno
- [ ] Win rate %
- [ ] Profit factor
- [ ] Average profit per trade
- [ ] Average loss per trade
- [ ] Max drawdown
- [ ] Sharpe ratio
- [ ] Confidenza media AI
- [ ] Correlazione confidenza AI vs esito trade
- [ ] Latenza decisione AI (p50, p95, p99)
- [ ] Latenza esecuzione ordine (p50, p95, p99)
- [ ] Uptime %
- [ ] Numero errori API Gemini
- [ ] Numero errori connessione IBKR
- [ ] Costo API Gemini al giorno

### Durante Produzione
- [ ] Tutte le metriche di paper trading
- [ ] P&L giornaliero
- [ ] P&L settimanale
- [ ] P&L mensile
- [ ] ROI %
- [ ] Capitale totale

---

## ⚠️ Checkpoint Obbligatori

| Checkpoint | Condizione | Azione se Fallito |
|------------|------------|-------------------|
| **Fine Fase 2** | Connessione IBKR stabile | STOP - Debug connessione |
| **Fine Fase 3** | API Gemini funzionante | STOP - Verificare API key |
| **Fine Fase 5** | Tutti i limiti validati | STOP - Fix Risk Manager |
| **Fine Fase 8** | Ciclo completo funzionante | STOP - Debug orchestratore |
| **Fine Fase 10** | Win rate paper > 50% | STOP - Ottimizzare strategia |
| **Prima Go-Live** | Tutti i criteri successo | STOP - Non procedere |

---

## 📚 Documentazione da Creare

- [ ] README.md - Overview e quick start
- [ ] ARCHITECTURE.md - Architettura dettagliata
- [ ] USER_MANUAL.md - Guida utente configurazione
- [ ] API_REFERENCE.md - Documentazione API endpoints
- [ ] TROUBLESHOOTING.md - Guida risoluzione problemi
- [ ] DEPLOYMENT.md - Procedura deploy dettagliata
- [ ] PERFORMANCE_REPORT.md - Template report performance
- [ ] AI_PROMPTS_GUIDE.md - Guida ottimizzazione prompt
- [ ] INCIDENT_RUNBOOK.md - Procedure emergenza

---

## 🔄 Review e Aggiornamenti

**Review settimanale:**
- [ ] Performance trading
- [ ] Stabilità sistema
- [ ] Costi operativi
- [ ] Ottimizzazioni necessarie

**Review mensile:**
- [ ] ROI vs target
- [ ] Aggiornamenti dipendenze
- [ ] Nuove feature AI
- [ ] Ottimizzazioni strategia

---

**Ultima modifica:** 2026-10-13  
**Prossimo aggiornamento:** Dopo inizio implementazione Fase 1
