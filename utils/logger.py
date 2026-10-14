"""
utils/logger.py - Logging strutturato per l'applicazione.

Configura structlog con output colorato per sviluppo e JSON per produzione.
Fornisce un logger pre-configurato importabile in tutti i moduli.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import structlog

from app.config import LOGS_DIR, get_settings


def setup_logging() -> None:
    """
    Configura il sistema di logging dell'applicazione.

    - Development: output colorato con rich su console
    - Production: output JSON su file + console
    """
    settings = get_settings()

    # Assicura che la directory logs esista
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    # Livello di log
    log_level = getattr(logging, settings.app_log_level, logging.DEBUG)

    # Processori comuni structlog
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if settings.is_debug:
        # --- Modalità Development ---
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    else:
        # --- Modalità Production ---
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Formatter per handler standard library
    formatter = structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=shared_processors,
    )

    # --- Console Handler ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)

    # --- File Handler ---
    log_file = LOGS_DIR / "ai-trader.log"
    file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
    file_handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
            foreign_pre_chain=shared_processors,
        )
    )
    file_handler.setLevel(logging.INFO)

    # --- Root Logger ---
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    root_logger.setLevel(log_level)

    # Silenzia logger troppo verbosi
    for noisy in ("urllib3", "httpx", "httpcore", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """
    Restituisce un logger strutturato con nome opzionale.

    Args:
        name: Nome del modulo/componente (es: "ibkr_connector", "ai_engine").

    Returns:
        Logger structlog pre-configurato.

    Esempio:
        >>> from utils.logger import get_logger
        >>> log = get_logger("my_module")
        >>> log.info("Operazione completata", symbol="XAUUSD", price=2650.50)
    """
    if name:
        return structlog.get_logger(name)
    return structlog.get_logger()
