#!/bin/sh
set -e

echo "=== Avvio Tradest AI Trading Bot ==="

# Se TRADEST_CONF_DIR è definita (es. /srv/docker_conf/configs/tradest_conf), prepara le directory
if [ -n "$TRADEST_CONF_DIR" ]; then
    echo "Directory configurazione esterna: $TRADEST_CONF_DIR"
    mkdir -p "$TRADEST_CONF_DIR" "$TRADEST_CONF_DIR/logs" "$TRADEST_CONF_DIR/data"
    
    # Se i file di default non esistono nella cartella esterna, copiali dai template
    for f in trading_params.json ai_prompts.json symbols.json; do
        if [ ! -f "$TRADEST_CONF_DIR/$f" ] && [ -f "/app/config/$f" ]; then
            echo "Copia template iniziale: $f -> $TRADEST_CONF_DIR/$f"
            cp "/app/config/$f" "$TRADEST_CONF_DIR/$f"
        fi
    done
fi

echo "Avvio uvicorn su 0.0.0.0:8080..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8080 --workers 1
