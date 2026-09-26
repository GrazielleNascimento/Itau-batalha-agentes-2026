"""Tools de memória. O consentimento é concedido na conversa, nunca pré-semeado."""

from __future__ import annotations

from datetime import UTC, datetime

from google.adk.tools.tool_context import ToolContext

from app.config import load_config
from app.memory.factory import get_memory_store
from app.tools.customer import NO_IDENTITY


def give_consent(tool_context: ToolContext) -> dict:
    """Registra o consentimento do cliente para guardar preferências entre conversas.

    Chame apenas depois de o cliente concordar explicitamente.

    Returns:
        consent_given_at com o instante do consentimento.
    """
    agora = datetime.now(UTC).isoformat()
    tool_context.state["consent_given_at"] = agora
    return {"consent_given_at": agora}


async def remember_preference(key: str, value: str, tool_context: ToolContext) -> dict:
    """Guarda uma preferência do cliente para as próximas conversas.

    Args:
        key: nome curto da preferência, por exemplo "canal" ou "objetivo".
        value: valor da preferência.

    Returns:
        saved indicando se gravou, e reason quando recusa.
    """
    cid = tool_context.state.get("customer_id")
    if not cid:
        return dict(NO_IDENTITY) | {"saved": False}
    consentimento = tool_context.state.get("consent_given_at")
    if not consentimento:
        return {
            "saved": False,
            "reason": "Sem consentimento registrado. Pergunte ao cliente e use give_consent.",
        }
    cfg = load_config()
    ok = await get_memory_store().save_preference(
        cid, key, value, consentimento, cfg.memory_ttl_days
    )
    return {"saved": ok, "reason": None if ok else "recusado pelo armazenamento"}


async def recall_profile(tool_context: ToolContext) -> dict:
    """Recupera as preferências guardadas do cliente, já descartando as expiradas.

    Returns:
        preferences com o que está vivo.
    """
    cid = tool_context.state.get("customer_id")
    if not cid:
        return dict(NO_IDENTITY) | {"preferences": {}}
    return {
        "preferences": (await get_memory_store().get_profile_summary(cid))[
            "preferences"
        ]
    }


async def forget_me(tool_context: ToolContext) -> dict:
    """Apaga tudo o que foi guardado sobre o cliente. Direito de exclusão da LGPD.

    Returns:
        deleted com quantos registros foram apagados.
    """
    cid = tool_context.state.get("customer_id")
    if not cid:
        return dict(NO_IDENTITY) | {"deleted": 0}
    apagados = await get_memory_store().delete_all(cid)
    # Revogar o consentimento junto: sem isto, a próxima preferência seria
    # gravada sem perguntar nada, logo depois de o agente confirmar a exclusão.
    # Atribuição em vez de pop(): o State do ADK não tem pop nem __delitem__,
    # e o gate de consentimento testa por valor falsy.
    tool_context.state["consent_given_at"] = ""
    return {"deleted": apagados, "consent_revoked": True}
