"""Escolhe o backend de memória por MEMORY_BACKEND."""

from __future__ import annotations

import os
from typing import Any

from app.config import load_config
from app.memory.local import SqliteMemoryStore


def _exigir(nome: str) -> str:
    valor = os.getenv(nome)
    if not valor:
        raise ValueError(
            f"MEMORY_BACKEND=agent_engine exige {nome}. "
            "Rode: make switch-project PROJECT_ID=... MODE=vertex "
            "e defina GOOGLE_CLOUD_AGENT_ENGINE_ID (make agent-engine cria um)."
        )
    return valor


def get_memory_store() -> Any:
    modo = os.getenv("MEMORY_BACKEND", "local").strip().lower()

    if modo == "local":
        return SqliteMemoryStore(load_config().data_dir / "memory.db")

    if modo == "agent_engine":
        # Ordem deliberada: o id é o que distingue "configurado" de "esquecido".
        engine_id = _exigir("GOOGLE_CLOUD_AGENT_ENGINE_ID")
        projeto = _exigir("GOOGLE_CLOUD_PROJECT")
        # southamerica-east1: a sessão persiste o texto BRUTO do usuário. Sessão e
        # memória ficam no Brasil; só a inferência do modelo sai.
        location = os.getenv("MEMORY_LOCATION", "southamerica-east1")

        import vertexai
        from google.adk.memory.vertex_ai_memory_bank_service import (
            VertexAiMemoryBankService,
        )

        from app.memory.agent_engine import AgentEngineMemoryStore

        return AgentEngineMemoryStore(
            bank=VertexAiMemoryBankService(
                project=projeto, location=location, agent_engine_id=engine_id
            ),
            memories_api=vertexai.Client(
                project=projeto, location=location
            ).agent_engines.memories,
            engine_name=f"projects/{projeto}/locations/{location}/reasoningEngines/{engine_id}",
        )

    raise ValueError(
        f"MEMORY_BACKEND desconhecido: {modo!r}. Use 'local' ou 'agent_engine'."
    )
