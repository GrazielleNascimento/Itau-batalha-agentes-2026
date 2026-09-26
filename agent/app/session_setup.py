"""Semeadura de identidade para demonstração.

Em produção o customer_id vem do canal autenticado, nunca de configuração. Isto
existe porque o playground cria sessões com o estado vazio, e sem identidade
nenhuma tool de dados responde.

O consentimento NÃO é semeado de propósito: a demo precisa mostrar a recusa
antes e a gravação depois.
"""

from __future__ import annotations

import logging

from app.config import load_config
from app.datasources.factory import get_data_source

logger = logging.getLogger(__name__)


def seed_demo_identity(callback_context) -> None:
    """Preenche customer_id e suitability no estado, só em DEMO_MODE."""
    cfg = load_config()
    if not cfg.demo_mode:
        return
    estado = callback_context.state
    if estado.get("customer_id"):
        return
    perfil = get_data_source().get_customer(cfg.demo_customer_id)
    if perfil is None:
        logger.warning(
            "DEMO_CUSTOMER_ID=%s não existe na base. Rode `make data` ou corrija o .env.",
            cfg.demo_customer_id,
        )
        return
    estado["customer_id"] = cfg.demo_customer_id
    estado["suitability"] = perfil["suitability"]
