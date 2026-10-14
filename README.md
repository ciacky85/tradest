# Tradest - AI Trading Bot

**Progetto:** Trading automatico basato su intelligenza artificiale (Google Gemini Pro)  
**Data creazione:** 2026-10-14  
**Workspace:** `/home/vvelectron/VisualVibe Workdirs/tradest`

---

## 🎯 Obiettivo

Applicazione di trading automatico che utilizza **Google Gemini Pro** per decisioni dinamiche su **XAUUSD** (oro), con scalping aggressivo basato su analisi AI invece di algoritmi statici.

### Caratteristiche Principali

- ✅ **AI-Driven Trading** - Gemini Pro analizza mercato e decide strategie in tempo reale
- ✅ **Portfolio Real-Time** - Visualizzazione bilanci, posizioni e transazioni da IBKR
- ✅ **Gestione Rischi Rigida** - Budget limiti, stop-loss obbligatori, emergency stop
- ✅ **Integrazione IBKR** - Connessione al broker Interactive Brokers (192.168.1.212:4004)
- ✅ **Notifiche Telegram** - Integrazione con tradeBotNotify esistente
- ✅ **Containerizzato** - Deploy con Podman/Docker

---

## 📁 Struttura Progetto

```
tradest/
├── plans/                          # Documentazione pianificazione
│   ├── ai-trading-bot-project-plan.md          (48KB - Piano completo)
│   └── ai-trading-bot-todo-implementation.md   (14KB - Todo list)
├── app/                            # Applicazione principale (da creare)
├── core/                           # Moduli core (da creare)
├── data/                           # Data layer (da creare)
├── strategy/                       # Strategie trading (da creare)
├── integration/                    # Integrazioni esterne (da creare)
├── utils/                          # Utility (da creare)
├── config/                         # Configurazioni (da creare)
├── tests/                          # Test suite (da creare)
├── docker/                         # Containerizzazione (da creare)
├── logs/                           # Log applicazione (da creare)
└── README.md                       # Questo file
```

---

## 📚 Documentazione

### Piano di Progetto
[`plans/ai-trading-bot-project-plan.md`](plans/ai-trading-bot-project-plan.md) - **1637 righe**

Contiene:
- Panoramica completa del progetto
- Analisi sistema Nautilus esistente
- Architettura multi-layer dettagliata
- 10 moduli applicativi con interfacce
- Diagrammi Mermaid (architettura, flussi, sequenze)
- Integrazione IBKR, Gemini Pro, tradeBotNotify
- Containerizzazione Podman
- Configurazioni e parametri rigidi
- 11 fasi di implementazione
- Metriche di successo e KPI
- Gestione rischi e mitigazioni

### Todo List Implementazione
[`plans/ai-trading-bot-todo-implementation.md`](plans/ai-trading-bot-todo-implementation.md) - **383 righe**

Contiene:
- 200+ task organizzati in 11 fasi
- Checkpoint obbligatori tra fasi
- Criteri di successo per go-live
- Metriche da tracciare
- Documentazione da creare

---

## 🏗️ Architettura

```
AI Trading Bot Container
├── FastAPI Server (API + Dashboard)
├── Trading Orchestrator (Coordinamento)
├── Gemini AI Engine (Decisioni trading)
├── IBKR Connector (Connessione broker)
├── Portfolio Manager (Gestione portfolio)
├── Market Analyzer (Analisi mercato)
├── Risk Manager (Validazione rischi)
├── Order Executor (Esecuzione ordini)
├── Notification Client (Webhook tradeBotNotify)
└── SQLite Database (Persistenza)

↓ Connessioni esterne
├── IBKR Gateway (192.168.1.212:4004)
├── Google Gemini Pro API
└── tradeBotNotify (webhook notifiche)
```

---

## 🚀 Stack Tecnologico

| Componente | Tecnologia | Note |
|------------|-----------|------|
| **Linguaggio** | Python 3.12 | Compatibilità Nautilus Trader |
| **Framework** | FastAPI | API server e dashboard |
| **Trading SDK** | Nautilus Trader | Connessione IBKR |
| **AI Engine** | Google Gemini Pro 1.5 | Decisioni trading |
| **Database** | SQLite | Persistenza locale |
| **Scheduler** | APScheduler | Task periodici |
| **Container** | Podman/Docker | Deploy containerizzato |

---

## 🔒 Sicurezza e Gestione Rischi

### Protezioni Implementate

| Protezione | Valore Default XAUUSD |
|------------|----------------------|
| **Budget per trade** | $5,000 max |
| **Stop-loss obbligatorio** | 0.5% dal prezzo entry |
| **Take-profit automatico** | 1.0% dal prezzo entry |
| **Daily loss limit** | $500 max |
| **Emergency stop** | $1,000 daily loss |
| **AI confidence minima** | 0.70 (70%) |
| **Position size massima** | 2.0 oz oro |
| **Trading hours** | 08:00-22:00 Europe/Rome |

### Validazioni Risk Manager

Ogni strategia AI viene validata contro:
1. Budget disponibile
2. Tipo trading consentito (long/short/both)
3. Limiti posizione
4. Loss giornaliero
5. Confidenza AI minima
6. Orari di trading

---

## 📊 Integrazione con Sistema Esistente

### IBKR Gateway
- **Host:** 192.168.1.212
- **Porta:** 4004
- **Client ID:** 500 (dedicato, no conflitti con Nautilus)

### tradeBotNotify
- **Webhook:** http://192.168.1.212:9008/notify
- **Formato:** JSON compatibile con sistema esistente
- **Notifiche:** Telegram via bot esistente

---

## 🎯 Prossimi Passi

### Fase 1: Setup Base e Infrastruttura
Creare struttura directory, configurazioni, database SQLite e logging.

### Fase 2: Connessione IBKR
Implementare connessione al broker e lettura portfolio.

### Fase 3: Integrazione Gemini Pro
Connettere API Google Gemini e testare decisioni AI.

### Fase 4-11: Implementazione Completa
Seguire il piano dettagliato in [`plans/ai-trading-bot-todo-implementation.md`](plans/ai-trading-bot-todo-implementation.md)

---

## 📝 Comandi Quick Start

```bash
# Navigare al workspace
cd "/home/vvelectron/VisualVibe Workdirs/tradest"

# Leggere la documentazione
cat plans/ai-trading-bot-project-plan.md
cat plans/ai-trading-bot-todo-implementation.md

# Iniziare implementazione Fase 1
# (vedere todo list per task dettagliati)
```

---

## 🤝 Sviluppo

**Modalità:** Code Mode (implementazione)  
**Riferimenti:** Nautilus Trader, tradeBotNotify esistenti  
**Deployment:** Podman container effimeri per testing

---

## 📖 Riferimenti

- [Nautilus Trader](https://nautilustrader.io/) - SDK trading
- [Google Gemini Pro](https://ai.google.dev/) - AI API
- [Interactive Brokers](https://www.interactivebrokers.com/) - Broker
- [FastAPI](https://fastapi.tiangolo.com/) - Framework web

---

**Progetto creato:** 2026-10-14  
**Ultima modifica:** 2026-10-14  
**Status:** Setup iniziale completato, pronto per implementazione
