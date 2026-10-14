# productContext.md - Tradest AI Trading Bot

## Visione e Indipendenza del Progetto
**Tradest** è un'applicazione completamente **indipendente ed autonoma** di trading automatico.
Non ha alcun collegamento o dipendenza software con Nautilus Trader o altri framework complessi: l'esperienza pregressa costituisce solo il background concettuale, ma il sistema è interamente progettato da zero.

## Decisioni di Trading basate su AI Live
Il cuore operativo dell'applicazione è il supporto in tempo reale di **Google Gemini AI**:
- Analisi continua dei dati e dello storico dei titoli (a partire da XAUUSD).
- Valutazione della situazione in tempo reale di mercato.
- Scelta dinamica tra posizioni **LONG**, **SHORT**, **HOLD** o chiusura anticipata della posizione.
- Selezione dinamica del modello da utilizzare (`gemini-1.5-pro`, `gemini-1.5-flash`, `gemini-2.0-flash-exp`) direttamente dall'interfaccia web.
- Determinazione automatica di Stop-Loss, Take-Profit e position sizing conforme ai vincoli di budget e di rischio dell'utente.

## Utente e Gestione
- Pannello Web UI moderno esposto sulla porta `18881`.
- Configurazione esterna unificata montata su `/srv/docker_conf/configs/tradest_conf`.
- Integrazione notifiche verso `tradeBotNotify` (porta 9008) per avvisi Telegram in tempo reale.
