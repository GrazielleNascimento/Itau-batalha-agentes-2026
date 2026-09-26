import os

import pytest
from google.adk.runners import InMemoryRunner
from google.genai import types

pytestmark = pytest.mark.llm

SEM_CREDENCIAL = not (
    os.getenv("GEMINI_API_KEY")
    or os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").lower() == "true"
)


async def _conversar(texto: str) -> tuple[str, list[str]]:
    from app.agent import app

    runner = InMemoryRunner(app=app)
    await runner.session_service.create_session(app_name=app.name, user_id="u", session_id="s")
    partes, agentes = [], []
    async for ev in runner.run_async(
        user_id="u",
        session_id="s",
        new_message=types.Content(role="user", parts=[types.Part(text=texto)]),
    ):
        agentes.append(ev.author)
        if ev.content and ev.content.parts:
            partes += [p.text for p in ev.content.parts if p.text]
    return " ".join(p for p in partes if p), agentes


@pytest.mark.skipif(SEM_CREDENCIAL, reason="precisa de GEMINI_API_KEY ou Vertex")
async def test_saudacao_e_respondida_pelo_orquestrador():
    resposta, _ = await _conversar("olá")
    assert resposta.strip()


@pytest.mark.skipif(SEM_CREDENCIAL, reason="precisa de GEMINI_API_KEY ou Vertex")
async def test_pergunta_conceitual_vai_para_o_educador():
    _, agentes = await _conversar("o que são juros compostos?")
    assert "educator" in agentes


@pytest.mark.skipif(SEM_CREDENCIAL, reason="precisa de GEMINI_API_KEY ou Vertex")
async def test_pergunta_numerica_usa_tool_e_devolve_valor():
    # Verificação da Fase 3 do HANDOFF.
    resposta, agentes = await _conversar("quanto gastei com mercado nos últimos 3 meses?")
    assert "analyst" in agentes
    assert any(c.isdigit() for c in resposta)
