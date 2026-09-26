import asyncio
from collections.abc import AsyncGenerator

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import InMemoryRunner
from google.genai import types

from app.tools import actions


class ChamaAcao(BaseLlm):
    model: str = "fake-model"

    async def generate_content_async(
        self, llm_request, stream=False
    ) -> AsyncGenerator[LlmResponse, None]:
        ja_chamou = any(
            p.function_response for c in (llm_request.contents or []) for p in (c.parts or [])
        )
        if ja_chamou:
            yield LlmResponse(content=types.Content(role="model", parts=[types.Part(text="fim")]))
        else:
            yield LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[
                        types.Part(
                            function_call=types.FunctionCall(
                                name="propose_action",
                                args={"action_type": "transfer", "details": "R$100"},
                            )
                        )
                    ],
                )
            )


def test_tool_exige_confirmacao():
    assert actions.PROPOSE_ACTION_TOOL._require_confirmation is True


def test_corpo_nao_executa_sem_confirmacao():
    actions.EXECUTED.clear()
    agente = Agent(
        name="a", model=ChamaAcao(), instruction="t", tools=[actions.PROPOSE_ACTION_TOOL]
    )
    runner = InMemoryRunner(app=App(name="a", root_agent=agente))

    async def rodar():
        await runner.session_service.create_session(app_name="a", user_id="u", session_id="s")
        pediu = False
        async for ev in runner.run_async(
            user_id="u",
            session_id="s",
            new_message=types.Content(role="user", parts=[types.Part(text="transfira")]),
        ):
            if getattr(ev, "actions", None) and getattr(
                ev.actions, "requested_tool_confirmations", None
            ):
                pediu = True
        return pediu

    assert asyncio.run(rodar()) is True
    assert actions.EXECUTED == []
