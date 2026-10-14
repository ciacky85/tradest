"""
integration/gemini_client.py - Client per Google Gemini API.

Supporta:
- Autenticazione con API Key
- Interrogazione modelli disponibili (gemini-1.5-pro, gemini-1.5-flash, ecc.)
- Selezione dinamica del modello runtime
- Generazione risposte strutturate JSON per trading
- Test di connessione e chat di verifica
"""

from __future__ import annotations

import json
from typing import Any, Optional

import httpx

from app.config import get_settings
from app.models import AITradeStrategy, TradeAction
from utils.logger import get_logger

logger = get_logger("gemini_client")

# Modelli standard di fallback se l'API non risponde all'endpoint di discovery
DEFAULT_FALLBACK_MODELS = [
    {
        "name": "models/gemini-2.5-flash",
        "displayName": "Gemini 2.5 Flash (Consigliato - Nuova Quota)",
        "description": "Modello di ultimissima generazione, altamente efficiente con quote separate",
    },
    {
        "name": "models/gemini-2.0-flash",
        "displayName": "Gemini 2.0 Flash",
        "description": "Modello ad alte prestazioni e bassa latenza",
    },
    {
        "name": "models/gemini-1.5-flash",
        "displayName": "Gemini 1.5 Flash",
        "description": "Modello ultra-veloce ed efficiente per scalping",
    },
    {
        "name": "models/gemini-1.5-pro",
        "displayName": "Gemini 1.5 Pro",
        "description": "Modello per ragionamento complesso (può richiedere tier a pagamento per rate limit elevati)",
    },
]


class GeminiClient:
    """Client asincrono per l'API Google Gemini Generative Language."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.gemini_api_key
        self.model = model or settings.gemini_model
        # Rimuove prefisso "models/" se già presente per coerenza con l'URL di generazione
        self._normalize_model_name()

    def _normalize_model_name(self) -> None:
        if self.model and self.model.startswith("models/"):
            self.model = self.model.replace("models/", "")

    def set_api_key(self, api_key: str) -> None:
        """Aggiorna l'API key."""
        self.api_key = api_key.strip()

    def set_model(self, model: str) -> None:
        """Aggiorna il modello selezionato."""
        self.model = model.strip().replace("models/", "")

    async def list_available_models(self) -> list[dict[str, Any]]:
        """
        Recupera dinamicamente la lista dei modelli supportati dall'account Google.
        Utilizza l'endpoint REST ufficiale: https://generativelanguage.googleapis.com/v1beta/models
        """
        if not self.api_key:
            return DEFAULT_FALLBACK_MODELS

        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={self.api_key}"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    models = data.get("models", [])
                    # Filtra solo modelli che supportano 'generateContent'
                    gen_models = [
                        m for m in models
                        if "generateContent" in m.get("supportedGenerationMethods", [])
                    ]
                    logger.info("Modelli Gemini recuperati con successo", count=len(gen_models))
                    return gen_models or DEFAULT_FALLBACK_MODELS
                else:
                    logger.warning(
                        "Impossibile listare modelli da Gemini API",
                        status=resp.status_code,
                        detail=resp.text,
                    )
                    return DEFAULT_FALLBACK_MODELS
        except Exception as e:
            logger.error("Errore chiamata discovery modelli Gemini", error=str(e))
            return DEFAULT_FALLBACK_MODELS

    async def test_connection(self) -> dict[str, Any]:
        """
        Invia un prompt di test veloce a Gemini per validare l'autenticazione
        e la corretta risposta del modello selezionato.
        """
        if not self.api_key:
            return {
                "success": False,
                "error": "API Key Google Gemini mancante. Inserisci la tua API Key nelle impostazioni.",
            }

        self._normalize_model_name()
        active_model = self.model or "gemini-1.5-pro"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{active_model}:generateContent?key={self.api_key}"

        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": "Sei connesso al sistema Tradest AI. Rispondi confermando la connessione in una sola riga."
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 100,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    try:
                        reply = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    except (KeyError, IndexError):
                        reply = "Connessione riuscita (formato risposta non standard)"
                    return {
                        "success": True,
                        "model": active_model,
                        "reply": reply,
                        "status_code": 200,
                    }
                elif resp.status_code == 429:
                    error_msg = (
                        f"Quota API superata (429) per il modello '{active_model}'. "
                        "Questo accade tipicamente sul free-tier di Google AI Studio (limite RPM/RPD) "
                        "oppure se il modello scelto ha esaurito la quota disponibile. "
                        "Prova a selezionare 'gemini-1.5-flash' o attendere qualche minuto."
                    )
                    logger.warning("Gemini API quota exceeded 429", model=active_model)
                    return {
                        "success": False,
                        "model": active_model,
                        "error": error_msg,
                        "status_code": 429,
                        "raw_detail": resp.text,
                    }
                else:
                    return {
                        "success": False,
                        "model": active_model,
                        "error": resp.text,
                        "status_code": resp.status_code,
                    }
        except Exception as e:
            return {"success": False, "model": active_model, "error": str(e)}

    async def generate_trade_analysis(self, prompt: str, system_instruction: Optional[str] = None) -> dict[str, Any]:
        """
        Invia un prompt di analisi di trading al modello Gemini configurato.
        Richiede output in formato JSON strutturato.
        """
        if not self.api_key:
            raise ValueError("Google Gemini API Key non impostata.")

        self._normalize_model_name()
        active_model = self.model or "gemini-1.5-pro"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{active_model}:generateContent?key={self.api_key}"

        payload: dict[str, Any] = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 2048,
                "responseMimeType": "application/json",
            },
        }

        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 429:
                logger.error("Errore 429 Quota Exceeded durante simulazione", model=active_model)
                raise RuntimeError(
                    f"Errore 429 Quota Exceeded: Il modello '{active_model}' ha raggiunto il limite di richieste/quota dell'API key. "
                    "Seleziona un modello con rate limit più elevato (es. 'gemini-1.5-flash') o attendi il reset."
                )
            elif resp.status_code != 200:
                logger.error("Errore risposta Gemini API", status=resp.status_code, text=resp.text)
                raise RuntimeError(f"Errore Gemini API ({resp.status_code}): {resp.text}")

            data = resp.json()
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"]

            try:
                parsed = json.loads(raw_text)
                return parsed
            except json.JSONDecodeError:
                # Tentativo pulizia markdown ```json ... ```
                clean = raw_text.strip()
                if clean.startswith("```json"):
                    clean = clean[7:]
                if clean.startswith("```"):
                    clean = clean[3:]
                if clean.endswith("```"):
                    clean = clean[:-3]
                return json.loads(clean.strip())


# Singleton GeminiClient
_gemini_client: Optional[GeminiClient] = None


def get_gemini_client() -> GeminiClient:
    """Restituisce il singleton GeminiClient."""
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = GeminiClient()
    return _gemini_client
