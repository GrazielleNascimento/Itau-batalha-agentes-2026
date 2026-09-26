"""Backend de memória gerenciado, sem chamar a nuvem.

Os dublês são `create_autospec` das classes REAIS: chamar um método com
argumento que não existe levanta TypeError aqui, no teste — e não em produção.
Foi exatamente assim que `add_memory(fact=...)` chegou ao Cloud Run: o fake
antigo aceitava **kw e escondia a divergência.
"""

import json
from unittest.mock import create_autospec

import pytest
from google.adk.memory.base_memory_service import SearchMemoryResponse
from google.adk.memory.memory_entry import MemoryEntry
from google.adk.memory.vertex_ai_memory_bank_service import VertexAiMemoryBankService
from google.genai import types

from app.memory.agent_engine import AgentEngineMemoryStore
from app.memory.factory import get_memory_store
from app.memory.local import SqliteMemoryStore

ENGINE = "projects/p/locations/us-central1/reasoningEngines/123"


def _bank():
    return create_autospec(VertexAiMemoryBankService, instance=True)


def _memories_api():
    import vertexai

    real = vertexai.Client(project="p", location="us-central1").agent_engines.memories
    return create_autospec(real, instance=True)


def _store(bank=None, api=None):
    return AgentEngineMemoryStore(
        bank=bank or _bank(), memories_api=api or _memories_api(), engine_name=ENGINE
    )


def test_padrao_e_local(monkeypatch):
    monkeypatch.delenv("MEMORY_BACKEND", raising=False)
    assert isinstance(get_memory_store(), SqliteMemoryStore)


def test_backend_desconhecido_falha_alto(monkeypatch):
    monkeypatch.setenv("MEMORY_BACKEND", "pombo-correio")
    with pytest.raises(ValueError, match="pombo-correio"):
        get_memory_store()


def test_agent_engine_exige_id(monkeypatch):
    monkeypatch.setenv("MEMORY_BACKEND", "agent_engine")
    monkeypatch.delenv("GOOGLE_CLOUD_AGENT_ENGINE_ID", raising=False)
    with pytest.raises(ValueError, match="GOOGLE_CLOUD_AGENT_ENGINE_ID"):
        get_memory_store()


def test_agent_engine_exige_projeto(monkeypatch):
    monkeypatch.setenv("MEMORY_BACKEND", "agent_engine")
    monkeypatch.setenv("GOOGLE_CLOUD_AGENT_ENGINE_ID", "123")
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    with pytest.raises(ValueError, match="GOOGLE_CLOUD_PROJECT"):
        get_memory_store()


async def test_consentimento_e_porta_tambem_no_gerenciado():
    bank = _bank()
    assert await _store(bank).save_preference("FICT-0001", "canal", "app", None, 90) is False
    bank.add_memory.assert_not_called()


async def test_grava_com_a_assinatura_real_do_servico():
    """Se o serviço mudar de assinatura, este teste quebra — em vez do deploy."""
    bank = _bank()
    ok = await _store(bank).save_preference("FICT-0001", "canal", "app", "2026-09-26T00:00:00", 90)
    assert ok is True
    bank.add_memory.assert_awaited_once()
    kw = bank.add_memory.await_args.kwargs
    assert kw["user_id"] == "FICT-0001"
    fato = json.loads(kw["memories"][0].content.parts[0].text)
    assert fato["key"] == "canal" and fato["consent_given_at"] == "2026-09-26T00:00:00"
    assert fato["expires_at"] > fato["created_at"]


def _entrada(fato: dict) -> MemoryEntry:
    return MemoryEntry(content=types.Content(parts=[types.Part(text=json.dumps(fato))]))


async def test_le_so_o_que_nao_expirou():
    bank = _bank()
    bank.search_memory.return_value = SearchMemoryResponse(
        memories=[
            _entrada({"key": "canal", "value": "app", "expires_at": "2999-01-01T00:00:00+00:00"}),
            _entrada({"key": "velha", "value": "x", "expires_at": "2000-01-01T00:00:00+00:00"}),
        ]
    )
    perfil = await _store(bank).get_profile_summary("FICT-0001")
    assert perfil["preferences"] == {"canal": "app"}


async def test_ignora_memoria_que_nao_e_nossa():
    """O Memory Bank pode gerar memórias próprias em texto livre; não são JSON."""
    bank = _bank()
    bank.search_memory.return_value = SearchMemoryResponse(
        memories=[MemoryEntry(content=types.Content(parts=[types.Part(text="usuário gosta de café")]))]
    )
    assert (await _store(bank).get_profile_summary("FICT-0001"))["preferences"] == {}


async def test_delete_all_apaga_so_as_do_cliente():
    from types import SimpleNamespace as NS

    api = _memories_api()
    api.list.return_value = iter([
        NS(name=f"{ENGINE}/memories/1", scope={"app_name": "123", "user_id": "FICT-0001"}),
        NS(name=f"{ENGINE}/memories/2", scope={"app_name": "123", "user_id": "FICT-0002"}),
        NS(name=f"{ENGINE}/memories/3", scope={"app_name": "123", "user_id": "FICT-0001"}),
    ])
    apagadas = await _store(api=api).delete_all("FICT-0001")
    assert apagadas == 2
    api.list.assert_called_once_with(name=ENGINE)
    apagados = sorted(c.kwargs["name"] for c in api.delete.call_args_list)
    assert apagados == [f"{ENGINE}/memories/1", f"{ENGINE}/memories/3"]


def test_fabrica_monta_o_store_gerenciado_com_a_assinatura_real(monkeypatch):
    """O ramo agent_engine da fábrica chegou a produção quebrado porque nenhum
    teste o exercitava: um replace no código falhou em silêncio e ninguém viu.
    Este teste constrói pelo caminho real, com as dependências espelhadas."""
    import vertexai

    monkeypatch.setenv("MEMORY_BACKEND", "agent_engine")
    monkeypatch.setenv("GOOGLE_CLOUD_AGENT_ENGINE_ID", "123")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "proj")
    monkeypatch.setenv("MEMORY_LOCATION", "southamerica-east1")

    real_memories = vertexai.Client(project="proj", location="southamerica-east1").agent_engines.memories
    fake_client = create_autospec(vertexai.Client, instance=True)
    fake_client.agent_engines.memories = create_autospec(real_memories, instance=True)
    monkeypatch.setattr("vertexai.Client", lambda **kw: fake_client)
    monkeypatch.setattr(
        "google.adk.memory.vertex_ai_memory_bank_service.VertexAiMemoryBankService",
        lambda **kw: create_autospec(VertexAiMemoryBankService, instance=True),
    )

    store = get_memory_store()
    assert isinstance(store, AgentEngineMemoryStore)
    assert store._engine == "projects/proj/locations/southamerica-east1/reasoningEngines/123"
    assert store._scope == "123"
