"""Agente proativo: um evento externo dispara uma mensagem ao cliente.

Cobre o "momento de atuação" — o agente fala quando algo acontece, em vez de
esperar o cliente perguntar.

Segurança: um evento vem de um chamador de sistema autenticado (Pub/Sub push com
OIDC), não do usuário. O `customer_id` dele é confiável e vai para o ESTADO da
sessão — nunca para o texto do prompt. A D2 continua valendo: o modelo não recebe
identificador no contexto.

Os campos de texto livre do evento são dado de terceiro, como a descrição de um
Pix, e passam pelo mesmo guard de injection.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.callbacks.injection import detect_injection

SANITIZED = "[conteúdo removido: instrução suspeita no evento]"

EVENT_TYPES: dict[str, str] = {
    "salary_received": (
        "O salário do cliente acabou de cair na conta{amount}. Cumprimente de forma breve "
        "e ofereça ajuda para planejar o mês, sem prometer nada que você não possa calcular."
    ),
    "spending_spike": (
        "Os gastos do cliente subiram de forma atípica{category}{amount}. Avise com cuidado, "
        "sem alarmismo, e ofereça olhar o extrato junto."
    ),
    "invoice_due_soon": (
        "A fatura do cartão do cliente vence em breve{due_date}{amount}. Lembre com "
        "gentileza e ofereça comparar pagar à vista com parcelar."
    ),
}

EventType = Literal["salary_received", "spending_spike", "invoice_due_soon"]


class EventRequest(BaseModel):
    """Evento recebido em POST /events."""

    event_type: EventType
    customer_id: str = Field(min_length=1)
    details: dict[str, Any] = Field(default_factory=dict)


def _limpo(valor: Any) -> str:
    """Texto livre do evento é dado, não instrução."""
    texto = str(valor)
    return SANITIZED if detect_injection(texto).blocked else texto


def build_event_prompt(event_type: str, details: dict[str, Any]) -> str:
    """Monta a instrução do evento. Nunca inclui identificador de cliente."""
    modelo = EVENT_TYPES.get(event_type)
    if modelo is None:
        return _desconhecido(event_type)

    partes = {"amount": "", "category": "", "due_date": ""}
    if (valor := details.get("amount")) is not None:
        partes["amount"] = f", no valor de R$ {float(valor):.2f}"
    if (cat := details.get("category")) is not None:
        partes["category"] = f", na categoria {_limpo(cat)}"
    if (venc := details.get("due_date")) is not None:
        partes["due_date"] = f", em {_limpo(venc)}"
    # details pode trazer customer_id; ele é deliberadamente ignorado aqui.
    return modelo.format(**partes)


def _desconhecido(event_type: str) -> str:
    raise ValueError(
        f"Tipo de evento desconhecido: {event_type!r}. Conhecidos: {', '.join(EVENT_TYPES)}."
    )
