# systemPatterns.md - AI Trading Bot

## Architettura del Sistema
Il sistema adotta un'architettura a livelli (layered architecture) fortemente disaccoppiata:

```
[ FastAPI HTTP Server ]
          │
[ Core Engine / Orchestrator ]
   ├── [ AI Engine (Gemini Pro) ]
   └── [ Scheduler (APScheduler 30s) ]
          │
[ Strategy Layer ]
   ├── [ Market Analyzer ]
   ├── [ Risk Manager ] (Gatekeeper vincolante)
   └── [ Order Executor ]
          │
[ Data Layer ]
   ├── [ IBKR Connector ] (Client ID 500, porta 4004)
   ├── [ Portfolio Manager ]
   └── [ Database SQLite ]
```

## Pattern Chiave
1. **Gatekeeper Pattern (Risk Manager):** Nessun ordine viene inviato al broker senza passare attraverso la validazione rigida e deterministica del Risk Manager, indipendentemente dalla confidenza dell'AI.
2. **Singleton Settings & DB:** Le configurazioni e l'accesso al database sono gestiti tramite pattern singleton con istanziazione lazy.
3. **Async-First:** Tutte le operazioni I/O (database, chiamate HTTP, broker, AI) sono asincrone per massimizzare la reattività.
4. **Structured Logging:** Utilizzo di `structlog` per tracciare ogni evento con attributi contestuali (simbolo, prezzo, decisione AI, confidenza).
