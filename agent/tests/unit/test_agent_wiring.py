from types import SimpleNamespace

import pytest
from google.adk.sessions.state import State

from app.prompts import load_prompt


def test_carrega_prompt_da_versao_ativa(monkeypatch):
    monkeypatch.setenv("PROMPT_VERSION", "v1")
    assert "TODO(jornada)" in load_prompt("orchestrator")


def test_versao_inexistente_falha_claro(monkeypatch):
    monkeypatch.setenv("PROMPT_VERSION", "v99")
    with pytest.raises(FileNotFoundError, match="v99"):
        load_prompt("orchestrator")


def test_app_registra_os_dois_plugins():
    from app.agent import app

    assert {p.name for p in app.plugins} == {"security", "audit"}


def test_subagentes_sao_analyst_e_educator():
    from app.agent import root_agent

    assert {a.name for a in root_agent.sub_agents} == {"analyst", "educator"}


def test_compactacao_de_contexto_ativa():
    from app.agent import app

    assert app.events_compaction_config is not None


def test_semeia_identidade_em_modo_demo(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("DEMO_CUSTOMER_ID", "FICT-0001")
    from app.session_setup import seed_demo_identity

    ctx = SimpleNamespace(state=State(value={}, delta={}))
    seed_demo_identity(ctx)
    assert ctx.state["customer_id"] == "FICT-0001"
    assert ctx.state["suitability"]


def test_nao_semeia_fora_do_modo_demo(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "false")
    from app.session_setup import seed_demo_identity

    ctx = SimpleNamespace(state=State(value={}, delta={}))
    seed_demo_identity(ctx)
    assert "customer_id" not in ctx.state


def test_nao_sobrescreve_identidade_existente(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    from app.session_setup import seed_demo_identity

    ctx = SimpleNamespace(state=State(value={"customer_id": "FICT-0007"}, delta={}))
    seed_demo_identity(ctx)
    assert ctx.state["customer_id"] == "FICT-0007"


def test_consentimento_nunca_e_semeado(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    from app.session_setup import seed_demo_identity

    ctx = SimpleNamespace(state=State(value={}, delta={}))
    seed_demo_identity(ctx)
    assert "consent_given_at" not in ctx.state


def test_demo_customer_id_inexistente_avisa(monkeypatch, caplog):
    # Review Focus 4: errar um dígito no pitch não pode virar vazio silencioso.
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("DEMO_CUSTOMER_ID", "FICT-9999")
    from app.session_setup import seed_demo_identity

    ctx = SimpleNamespace(state=State(value={}, delta={}))
    with caplog.at_level("WARNING"):
        seed_demo_identity(ctx)
    assert "FICT-9999" in caplog.text
    assert "customer_id" not in ctx.state
