# Tradest - AI Trading Bot

**Versione:** 1.0.3  
**Progetto:** Trading automatico basato su intelligenza artificiale (Google Gemini)  
**Data aggiornamento:** 2026-10-14  
**Workspace:** `/home/vvelectron/VisualVibe Workdirs/tradest`  
**GitHub Repository:** [`https://github.com/ciacky85/tradest`](https://github.com/ciacky85/tradest)  

---

## 🎯 Obiettivo del Progetto

Tradest è un'applicazione **completamente indipendente ed autonoma** che impiega l'intelligenza artificiale di **Google Gemini** per analizzare in tempo reale lo storico e le condizioni di mercato e determinare dinamicamente le posizioni di trading (**LONG**, **SHORT**, **HOLD**) su **XAUUSD** (oro spot) con rigorosa gestione del rischio (Stop-Loss, Take-Profit e position sizing).

### Caratteristiche Principali

- ✅ **Versione:** 1.0.3
- ✅ **100% Autonomo:** Nessun collegamento né dipendenza con software esterni; architettura leggera e modulare
- ✅ **Interactive Brokers Gateway:** Collegato a `192.168.1.212:4004` (Client ID 500)
- ✅ **AI Live Dynamic Decisions:** Analisi continua e scelte operative demandate a Google Gemini
- ✅ **Selezione Dinamica Modello:** Modello Gemini selezionabile da Web UI (`gemini-1.5-pro`, `gemini-1.5-flash`, `gemini-2.0-flash-exp`)
- ✅ **Dashboard Web:** Interfaccia grafica intuitiva per monitoraggio, test live e configurazione API Google
- ✅ **Stack Portainer Ready:** Esposizione su porta `18881` con configurazione unificata su `/srv/docker_conf/configs/tradest_conf` e `pull_policy: build` per evitare errori di registry pull
- ✅ **Gestione Rischi:** Budget massimo per trade ($5,000), Stop-Loss 0.5%, Take-Profit 1.0%, Daily Loss limit ($500), Emergency Stop

---

## 🚀 Deploy Rapido con Portainer

Consulta la guida completa in [`PORTAINER.md`](PORTAINER.md) per istruzioni dettagliate.

```bash
# Directory host richiesta
mkdir -p /srv/docker_conf/configs/tradest_conf
chmod -R 775 /srv/docker_conf/configs/tradest_conf
```

Stack Portainer compose path: `docker/docker-compose.portainer.yml`  
Porta accessibile da browser: `http://<IP-HOST>:18881/`
