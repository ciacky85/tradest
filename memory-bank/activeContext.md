# activeContext.md - Tradest AI Trading Bot

## Stato Attuale
- **Versione Corrente:** `1.7.0`
- **Data:** 2026-10-17
- **Repository GitHub:** [`https://github.com/ciacky85/tradest`](https://github.com/ciacky85/tradest)
- **Account GitHub:** `ciacky85`
- **Token GitHub:** Memorizzato in `/home/vvelectron/.github_token`
- **IBKR Gateway:** `192.168.1.212:4004` (VNC: `5900`, Client ID 500/dinamico, Account verificato: `DUR222070`)
- **Portainer Stack:** Porta `18881` esposta, volume esterno `/srv/docker_conf/configs/tradest_conf`
- **Web Dashboard & Tab Navigation:** Riorganizzata la dashboard in schermate e tab apribili separatamente:
  1. *Dashboard & Scalping:* Quadro generale portafoglio unificato con stato lavori in corso, metriche saldi real-time, frame di lancio scalping con parametro budget, verdetto AI, storico operazioni svolte e console log.
  2. *Tab Titoli:* Icone e loghi ufficiali ad alta risoluzione (Nvidia, Apple, Microsoft, Amazon, Tesla, Meta, Google, ecc.) con stato attivo/inattivo del bot in background per ciascun titolo.
  3. *Portafoglio Reale:* Schermata dedicata con saldo, buying power, posizioni aperte con P&L, ordini pendenti ed esecuzioni storiche da IBKR.
  4. *Cerca Asset / Titoli:* Finestra/schermata di ricerca per nome azienda, simbolo ticker o ISIN, con quote in tempo reale e pulsante di aggiunta a portafoglio/trading con relativo budget.
  5. *Gateway & Credenziali:* Schermate dedicate per la gestione delle connessioni (Omniroute/Google AI Studio e IBKR Gateway paper/live con credenziali salvabili).

## Note Operative
1. **Versione 1.7.0:**
   - Implementazione della nuova navigazione a schermate/tab in [`app/templates/index.html`](app/templates/index.html:1).
   - Nuovi endpoint API in [`app/main.py`](app/main.py:600): `/api/symbols/search` (ricerca su mercati via ticker/nome/ISIN), `/api/symbols/quote/{symbol}` (prezzo e variazione 24h) e `/api/symbols/add` (aggiunta di nuovi asset con configurazione e budget persistente).
   - Aggiunta funzione `save_symbols_config` in [`app/config.py`](app/config.py:202) per persistenza configurazione simboli tradabili.
   - Test di integrazione superati con successo: IA (Omniroute/Antigravity OK), IBKR Gateway (Paper account `DUR222070` con 4 posizioni OK).
2. **Versione 1.6.1:**
   - Risolto errore JavaScript `Cannot set properties of null (setting 'className')` ripristinando e proteggendo i riferimenti all'elemento [`ibkrStatusBadge`](app/templates/index.html:51) nell'header.
   - Risolto errore nell'analisi AI (`simulate_trade`): corretto import `asyncio` mancante in [`app/main.py`](app/main.py:17) e [`data/market_analyzer.py`](data/market_analyzer.py:14), aumentati i timeout di interrogazione modello per consentire il completamento dei payload complessi senza incorrere in TimeoutError.
   - Ottimizzata la gestione delle connessioni asincrone SQLite in [`data/database.py`](data/database.py:180) per prevenire deadlock durante le chiamate concorrenti.
2. **Versione 1.6.0:**
   - **Sequenza Tassativa Pre-Avvio Bot:** All'avvio di un bot per qualsiasi titolo, il sistema esegue obbligatoriamente e in sequenza: 1) refresh e sincronizzazione del portafoglio IBKR reale; 2) nuova analisi AI e di mercato fresca e contestualizzata in tempo reale; 3) validazione del budget e capienza buying power; 4) avvio effettivo del task di trading automatico. Questo impedisce categoricamente l'avvio su dati vecchi o non aggiornati.
   - **Frame Riassuntivo Operazioni Effettive:** Aggiunto frame sopra la console log dei bot che elenca in modo pulito e dettagliato solo le operazioni effettivamente svolte (LONG/SHORT), con colonne dedicate: Data e Ora, Tipo/Direzione, Azione (BUY/SELL), Quantità, Prezzo Esecuzione, Stop Loss, Take Profit, P&L e Stato/Dettagli.
   - Creata la tabella [`executed_operations`](data/database.py:112) e l'endpoint API [`/bot/operations`](app/main.py:739) filtrabile per simbolo, con polling integrato e sincronizzato nei rispettivi tab.
   - Rimosso il riquadro "Controllo Bot" in cima e posizionati nell'header lo stato IBKR e il pulsante di Stop Emergenza.
2. **Versione 1.5.0:** Riprogettata l'interfaccia di analisi e trading con Tab interattivi dedicati per ogni titolo a portafoglio (`XAUUSD`, `NVDA`, `SPCX`, `IB1T`). Risolto il refuso nel testo del pulsante che rimaneva statico su "XAUUSD": ora aggiorna dinamicamente l'etichetta `Analizza {simbolo} & Genera Strategia` sia durante che al termine dell'analisi. Ciascuna scheda mostra lo stato del bot (pallino animato verde o grigio) e memorizza/ripristina istantaneamente l'analisi, la decisione strategica, il budget e i log del titolo corrispondente via endpoint dedicato `/api/strategy/{symbol}`.
2. **Versione 1.4.0:** Integrato l'avvio e l'arresto del trading automatico direttamente all'interno della card di analisi del titolo. Creato il modulo [`MultiBotEngine`](strategy/bot_engine.py:32) che esegue task asincroni indipendenti in background per ciascun titolo.
2. **Versione 1.3.0:** Supporto completo alla selezione dinamica dello strumento finanziario (XAUUSD, NVDA, SPCX, IB1T) e configurazione/salvataggio del budget dedicato per titolo in SQLite (`symbols_budget`). Implementata logica tassativa di gestione del budget e quote intere (no frazioni).
2. **Versione 1.2.1:** Risolto definitivamente il problema dei segnaposto non valorizzati (supportati sia `{var}` che `{{var}}` e forzato auto-sync di `ai_prompts.json` su modifiche). Implementata l'importazione preventiva del portafoglio IBKR (`DUR222070`) con isolamento e valutazione specifica della posizione aperta su XAUUSD prima di elaborare la strategia di scalping.
2. **Versione 1.2.0:** Implementato modulo [`MarketAnalyzer`](data/market_analyzer.py:59) (estrazione barre storiche 30 giorni e 7 giorni da IBKR, calcolo EMA, RSI, MACD, ATR, Bollinger, range e supporti/resistenze) e modulo [`ScalpingStrategyManager`](strategy/scalping_strategy.py:32). Integrata validazione pre-avvio del trading automatico.
2. **Versione 1.1.0:** Configurato token Omniroute dedicato `sk-92fbd7ff0bd42a7d-82e301-62dbdb1f` verificato con successo su `http://192.168.1.212:9292/v1` (modello `carlo-gemini` e `gemini-3.8-flash-tiered`). Aggiornata UI per evitare sovrascritture accidentali della chiave.
2. **Versione 1.0.9:** Supporto nativo al gateway Omniroute / Antigravity su `http://192.168.1.212:9292/v1` con modelli `carlo-gemini`, `antigravity/gemini-3.8-flash-tiered`, ecc. Risolto definitivamente il problema delle quote 429! Credenziali IBKR precompilate di default su `lhungq693` / `secretpaper`.
2. **Versione 1.0.8:** Estrazione e visualizzazione completa dei dati del portafoglio IBKR (posizioni dettagliate con P&L, prezzi di mercato e carico, tipo strumento e borsa; transazioni ed ordini). Normalizzazione e diagnostica per modello `gemini-2.5-flash` e risoluzione gestione quote 429.
2. **Versione 1.0.7:** Impostate le credenziali predefinite `nautilususer` e `D90c1df4t@!` per l'utenza IBKR. Impostato di default il modello `gemini-2.5-flash` per superare i limiti di quota 429 di Gemini 1.5 Pro.
2. **Versione 1.0.6:** Completato l'allineamento globale dell'indirizzo IP di Interactive Brokers Gateway a `192.168.1.212:4004` su tutta la codebase (Docker compose, Portainer stack, config Pydantic, template HTML e documentazione).
2. **Versione 1.0.5:** Connessione verificata con successo dal vivo con `ib_insync` su `192.168.1.212:4004`, rilevato account `DUR222070`, saldo €990.477 e 4 posizioni reali.
3. **Versione 1.0.4:** Implementata gestione completa credenziali IBKR (username/password) e modalità Paper/Live trading. Aggiunto client [`ibkr_client.py`](../integration/ibkr_client.py:1) con connessione asincrona a Gateway/TWS, estrazione portfolio e posizioni. Migliorata gestione errori 429 quota Gemini con messaggi dettagliati e fallback modelli. Dashboard estesa con sezione configurazione IBKR, test connessione e visualizzazione dati portafoglio.
2. Versione 1.0.3: Risolto l'errore di Portainer "compose pull operation failed: denied". Configurato `pull_policy: build` e aggiunto workflow GitHub Actions in `.github/workflows/docker-publish.yml` per build/pubblicazione su GHCR.
2. In Portainer, disattivare il toggle "Re-pull image" se si esegue il build dal repository Git.
3. Host di Interactive Brokers Gateway impostato su `192.168.1.212:4004`.
4. Il volume esterno host `/srv/docker_conf/configs/tradest_conf` è montato in `/tradest_conf`, isolando il codice Python sorgente ed evitando sovrascritture di moduli.
5. Ad ogni modifica completata: incrementare il numero di versione, riportarlo nei file `.md`, eseguire il commit/push su Git e segnalare la versione all'utente.
