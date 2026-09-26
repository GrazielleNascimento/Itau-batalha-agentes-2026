"""Memória de longo prazo no Vertex AI Memory Bank.

Mesmo contrato do SqliteMemoryStore: consentimento é porta, TTL vale, e
delete_all apaga. O que muda é onde o dado vive — num serviço gerenciado,
compartilhado entre instâncias, em vez de num arquivo dentro do container.

Assinaturas verificadas por introspecção da biblioteca instalada (regra 6):
  add_memory(*, app_name, user_id, memories: Sequence[MemoryEntry])   [async]
  search_memory(*, app_name, user_id, query) -> .memories              [async]
O serviço do ADK não expõe remoção; delete_all usa o cliente por baixo
(agent_engines.memories.list / delete), porque direito de exclusão não é opcional.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from google.adk.memory.memory_entry import MemoryEntry
from google.genai import types

logger = logging.getLogger(__name__)


class AgentEngineMemoryStore:
    """Preferências no Memory Bank, com as mesmas regras de governança.

    O Memory Bank guarda fatos em texto; empacotamos a preferência como JSON e
    carregamos consentimento e validade junto, porque a política é nossa e
    precisa viajar com o dado.
    """

    def __init__(self, bank: Any, memories_api: Any, engine_name: str) -> None:
        self._bank = bank
        self._memories = memories_api  # vertexai.Client().agent_engines.memories
        self._engine = engine_name  # projects/.../reasoningEngines/<id>
        self._scope = engine_name.rsplit("/", 1)[-1]

    async def save_preference(
        self,
        customer_id: str,
        key: str,
        value: str,
        consent_given_at: str | None,
        ttl_days: int,
    ) -> bool:
        if not consent_given_at:
            return False
        agora = datetime.now(UTC)
        fato = json.dumps(
            {
                "key": key,
                "value": value,
                "created_at": agora.isoformat(),
                "expires_at": (agora + timedelta(days=ttl_days)).isoformat(),
                "consent_given_at": consent_given_at,
            },
            ensure_ascii=False,
        )
        await self._bank.add_memory(
            app_name=self._scope,
            user_id=customer_id,
            memories=[
                MemoryEntry(content=types.Content(parts=[types.Part(text=fato)]))
            ],
        )
        return True

    async def _vivas(self, customer_id: str) -> list[dict]:
        agora = datetime.now(UTC).isoformat()
        resposta = await self._bank.search_memory(
            app_name=self._scope, user_id=customer_id, query="preferência do cliente"
        )
        vivas: list[dict] = []
        for entrada in resposta.memories:
            texto = "".join(p.text or "" for p in (entrada.content.parts or []))
            try:
                dado = json.loads(texto)
            except ValueError:
                continue  # memória que não é nossa (ex.: gerada pelo próprio banco)
            if dado.get("expires_at", "") > agora:
                vivas.append(dado)
        return vivas

    async def get_profile_summary(self, customer_id: str) -> dict:
        vivas = await self._vivas(customer_id)
        return {
            "preferences": {d["key"]: d["value"] for d in vivas},
            "expires_at": {d["key"]: d["expires_at"] for d in vivas},
        }

    async def delete_all(self, customer_id: str) -> int:
        """Direito de exclusão: apaga toda memória cujo escopo pertence ao cliente."""
        apagadas = 0
        for memoria in self._memories.list(name=self._engine):
            if customer_id in (memoria.scope or {}).values():
                self._memories.delete(name=memoria.name)
                apagadas += 1
        return apagadas
