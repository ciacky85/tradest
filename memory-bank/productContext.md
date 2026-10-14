# productContext.md - AI Trading Bot

## Perché Esiste il Progetto
L'AI Trading Bot è un sistema automatizzato di trading ad alta frequenza (scalping) specializzato su **XAUUSD** (oro spot vs dollaro americano) che supera i limiti degli algoritmi tradizionali basati su regole rigide introducendo **Google Gemini Pro** come motore decisionale in tempo reale.

## Problemi che Risolve
1. **Adattabilità al mercato:** I mercati volatili come l'oro mettono in crisi i sistemi statici basati solo su incroci di medie mobili. Gemini Pro analizza il contesto complessivo (sentiment, momentum, livelli chiave).
2. **Controllo del rischio rigido:** Separazione netta tra suggerimento AI ed esecuzione ordini: il Risk Manager valida ogni decisione contro limiti di budget ($5,000/trade), stop-loss obbligatori (0.5%), perdita massima giornaliera ($500) ed emergency stop ($1,000).
3. **Visibilità e Notifiche:** Integrazione con l'infrastruttura esistente IBKR Gateway e `tradeBotNotify` per notifiche istantanee via Telegram.

## Utenti e Stakeholder
- Operatore di trading: visualizzazione portfolio, controllo bot (start/stop/emergency), ricezione alert Telegram.
