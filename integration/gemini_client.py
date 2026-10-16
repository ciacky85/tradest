"""
integration/gemini_client.py - Client universale per AI (Omniroute / Antigravity Gateway & Google AI Studio).

Supporta:
- Provider "omniroute": Gateway AI locale/remoto compatibile OpenAI (es. Antigravity su http://192.168.1.212:9292/v1)
  con modelli dedicati (carlo-gemini, antigravity/gemini-3.8-flash-tiered, antigravity/gemini-3-flash, ecc.)
  SENZA problemi di quota o limiti 429!
- Provider "google": Endpoint REST nativo Google AI Studio (generativelanguage.googleapis.com)
- Selezione dinamica runtime del provider e del modello
- Test di connessione e simulazione decisioni strategiche di trading in formato JSON strutturato
"""

from __future__ import annotations

import json
from typing import Any, Optional

import httpx

from app.config import get_settings
from app.models import AITradeStrategy, TradeAction
from utils.logger import get_logger

logger = get_logger("ai_client")

# Modelli standard consigliati per Omniroute / Antigravity
DEFAULT_OMNIROUTE_MODELS = [
    {
        "name": "carlo-gemini",
        "displayName": "Carlo Gemini (Omniroute - Zero Quota Limit)",
        "description": "Modello Gemini su Omniroute senza limiti di quota 429",
    },
    {
        "name": "antigravity/gemini-3.8-flash-tiered",
        "displayName": "Antigravity Gemini 3.8 Flash Tiered",
        "description": "Modello Gemini 3.8 avanzato ad altissima velocità e zero quota issues",
    },
    {
        "name": "antigravity/gemini-3-flash",
        "displayName": "Antigravity Gemini 3 Flash",
        "description": "Gemini 3 Flash ottimizzato per scalping ad alta frequenza",
    },
    {
        "name": "carlo-deepseek-PRO",
        "displayName": "Carlo DeepSeek PRO",
        "description": "Modello di ragionamento finanziario avanzato",
    },
    {
        "name": "antigravity/claude-sonnet-4-6",
        "displayName": "Claude Sonnet 4.6 (Omniroute)",
        "description": "Capacità analitiche e logiche estreme",
    },
]

# Modelli standard di fallback per Google AI Studio
DEFAULT_GOOGLE_MODELS = [
    {
        "name": "models/gemini-2.5-flash",
        "displayName": "Gemini 2.5 Flash (Google AI Studio)",
        "description": "Modello di ultimissima generazione ad alta efficienza",
    },
    {
        "name": "models/gemini-2.0-flash",
        "displayName": "Gemini 2.0 Flash",
        "description": "Modello ad alte prestazioni e bassa latenza",
    },
    {
        "name": "models/gemini-1.5-flash",
        "displayName": "Gemini 1.5 Flash",
        "description": "Modello ultra-veloce ed efficiente",
    },
    {
        "name": "models/gemini-1.5-pro",
        "displayName": "Gemini 1.5 Pro",
        "description": "Modello ad alte prestazioni per ragionamento complesso",
    },
]


class GeminiClient:
    """Client asincrono universale per Omniroute (OpenAI API) e Google Gemini REST."""

    def __init__(
        self,
        provider: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        settings = get_settings()
        self.provider: str = provider or settings.ai_provider
        self.base_url: str = base_url or settings.ai_base_url
        self.api_key: str = api_key or (settings.ai_api_key if self.provider == "omniroute" else settings.gemini_api_key)
        self.model: str = model or settings.gemini_model
        self._normalize_model_name()

    def _normalize_model_name(self) -> None:
        if self.provider == "google":
            if self.model and self.model.startswith("models/"):
                self.model = self.model.replace("models/", "")
            if self.model in ("3.8", "gemini-3.8", "3.8-pro", "gemini-3.8-pro", "sonnet-3.8"):
                self.model = "gemini-2.5-flash"

    def set_provider(self, provider: str, base_url: Optional[str] = None, api_key: Optional[str] = None) -> None:
        """Aggiorna il provider (omniroute o google)."""
        self.provider = provider.lower().strip()
        if base_url:
            self.base_url = base_url.strip().rstrip("/")
        if api_key:
            self.api_key = api_key.strip()

    def set_api_key(self, api_key: str) -> None:
        """Aggiorna l'API key."""
        self.api_key = api_key.strip()

    def set_model(self, model: str) -> None:
        """Aggiorna il modello selezionato."""
        self.model = model.strip()
        self._normalize_model_name()

    async def list_available_models(self) -> list[dict[str, Any]]:
        """Recupera la lista dei modelli disponibili dal provider attivo."""
        if self.provider == "omniroute":
            # Endpoint OpenAI-compatible: /v1/models
            url = f"{self.base_url.rstrip('/')}/models"
            headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(url, headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        raw_models = data.get("data", [])
                        omni_models = []
                        for m in raw_models:
                            mid = m.get("id", "")
                            # Priorità e filtraggio per modelli Gemini e Antigravity
                            omni_models.append({
                                "name": mid,
                                "displayName": mid,
                                "description": f"Modello Omniroute: {mid}",
                            })
                        # Seleziona o ordina per portare in alto quelli gemini/antigravity
                        gemini_first = sorted(
                            omni_models,
                            key=lambda x: (
                                not ("gemini" in x["name"].lower() or "carlo" in x["name"].lower()),
                                x["name"]
                            )
                        )
                        return gemini_first if gemini_first else DEFAULT_OMNIROUTE_MODELS
            except Exception as e:
                logger.warning("Errore discovery modelli Omniroute, fallback su default", error=str(e))
            return DEFAULT_OMNIROUTE_MODELS

        else:
            # Endpoint Google AI Studio
            if not self.api_key:
                return DEFAULT_GOOGLE_MODELS

            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={self.api_key}"
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        data = resp.json()
                        models = data.get("models", [])
                        gen_models = [
                            m for m in models
                            if "generateContent" in m.get("supportedGenerationMethods", [])
                        ]
                        return gen_models if gen_models else DEFAULT_GOOGLE_MODELS
            except Exception as e:
                logger.warning("Errore recupero modelli Google, fallback", error=str(e))
            return DEFAULT_GOOGLE_MODELS

    async def test_connection(self) -> dict[str, Any]:
        """Invia un prompt di test al provider configurato."""
        if self.provider == "omniroute":
            return await self._test_omniroute()
        else:
            return await self._test_google()

    async def _test_omniroute(self) -> dict[str, Any]:
        """Test connessione con Omniroute / Antigravity Gateway (OpenAI Chat API)."""
        active_model = self.model or "carlo-gemini"
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": active_model,
            "messages": [
                {
                    "role": "user",
                    "content": "Conferma la connessione a Tradest rispondendo esattamente: 'Connessione Omniroute/Antigravity OK'",
                }
            ],
            "temperature": 0.1,
            "max_tokens": 60,
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    reply = data["choices"][0]["message"]["content"].strip()
                    return {
                        "success": True,
                        "provider": "omniroute",
                        "model": active_model,
                        "reply": reply,
                        "status_code": 200,
                    }
                else:
                    return {
                        "success": False,
                        "provider": "omniroute",
                        "model": active_model,
                        "error": f"Errore {resp.status_code}: {resp.text}",
                        "status_code": resp.status_code,
                    }
        except Exception as e:
            return {"success": False, "provider": "omniroute", "model": active_model, "error": str(e)}

    async def _test_google(self) -> dict[str, Any]:
        """Test connessione con Google AI Studio nativo."""
        if not self.api_key:
            return {
                "success": False,
                "error": "API Key Google Gemini mancante. Inserisci la tua API Key nelle impostazioni.",
            }

        self._normalize_model_name()
        active_model = self.model or "gemini-2.5-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{active_model}:generateContent?key={self.api_key}"

        payload = {
            "contents": [{"parts": [{"text": "Conferma la connessione rispondendo in una riga."}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 60},
        }

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    reply = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    return {
                        "success": True,
                        "provider": "google",
                        "model": active_model,
                        "reply": reply,
                        "status_code": 200,
                    }
                elif resp.status_code == 429:
                    return {
                        "success": False,
                        "provider": "google",
                        "model": active_model,
                        "error": f"Quota API Google 429 superata. Passa a provider 'Omniroute' per aggirare il limite!",
                        "status_code": 429,
                        "raw_detail": resp.text,
                    }
                else:
                    return {
                        "success": False,
                        "provider": "google",
                        "model": active_model,
                        "error": resp.text,
                        "status_code": resp.status_code,
                    }
        except Exception as e:
            return {"success": False, "provider": "google", "model": active_model, "error": str(e)}

    async def generate_trade_analysis(self, prompt: str, system_instruction: Optional[str] = None) -> dict[str, Any]:
        """Genera l'analisi strategica di trading richiedendo output JSON."""
        if self.provider == "omniroute":
            return await self._generate_omniroute(prompt, system_instruction)
        else:
            return await self._generate_google(prompt, system_instruction)

    async def _generate_omniroute(self, prompt: str, system_instruction: Optional[str] = None) -> dict[str, Any]:
        """Generazione tramite Omniroute (OpenAI API)."""
        active_model = self.model or "carlo-gemini"
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": active_model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 2048,
        }

        async with httpx.AsyncClient(timeout=75.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"Errore Omniroute API ({resp.status_code}): {resp.text}")

            data = resp.json()
            raw_text = data["choices"][0]["message"]["content"]
            return self._clean_and_parse_json(raw_text)

    async def _generate_google(self, prompt: str, system_instruction: Optional[str] = None) -> dict[str, Any]:
        """Generazione tramite Google AI Studio nativo."""
        if not self.api_key:
            raise ValueError("Google Gemini API Key non impostata.")

        self._normalize_model_name()
        active_model = self.model or "gemini-2.5-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{active_model}:generateContent?key={self.api_key}"

        payload: dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 2048,
                "responseMimeType": "application/json",
            },
        }

        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"Errore Google Gemini API ({resp.status_code}): {resp.text}")

            data = resp.json()
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
            return self._clean_and_parse_json(raw_text)

    def _clean_and_parse_json(self, raw_text: str) -> dict[str, Any]:
        """Pulisce blocchi markdown e parsa il dizionario JSON."""
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
