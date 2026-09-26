"""Contrato de memória de longo prazo.

Consentimento, TTL e direito de exclusão são regras de domínio, não
infraestrutura. Assíncrono porque o backend gerenciado é assíncrono, e uma
tool do ADK roda dentro do event loop — não dá para bloquear nele.
"""

from __future__ import annotations

from typing import Protocol


class MemoryStore(Protocol):
    async def save_preference(
        self,
        customer_id: str,
        key: str,
        value: str,
        consent_given_at: str | None,
        ttl_days: int,
    ) -> bool: ...
    async def get_profile_summary(self, customer_id: str) -> dict: ...
    async def delete_all(self, customer_id: str) -> int: ...
