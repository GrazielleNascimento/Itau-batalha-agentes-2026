"""Orquestrador e subagentes.

TODO(jornada): renomear e reescrever os subagentes conforme a jornada do evento.
Ao renomear o root agent, mude também agents-cli-manifest.yaml — o nome vive nos
dois lugares e a telemetria reporta o do código como gen_ai.agent.name.
"""

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.apps.app import EventsCompactionConfig
from google.adk.models import Gemini
from google.genai import types

from app.config import assert_flags_coerentes, load_config
from app.plugins.audit_plugin import AuditPlugin
from app.plugins.security_plugin import SecurityPlugin
from app.prompts import load_prompt
from app.session_setup import seed_demo_identity
from app.tools.actions import PROPOSE_ACTION_TOOL
from app.tools.customer import (
    get_account_summary,
    get_card_summary,
    get_customer_profile,
    get_goals,
    get_transactions,
)
from app.tools.finance import (
    compare_revolving_vs_installments,
    compound_interest,
    time_to_reach_goal,
)
from app.tools.knowledge import search_knowledge
from app.tools.memory_tools import (
    forget_me,
    give_consent,
    recall_profile,
    remember_preference,
)

# Falha na importação se alguma flag estiver ligada sem implementação atrás.
# Melhor o app não subir do que subir fingindo ter proteção.
assert_flags_coerentes()
_cfg = load_config()


def _model() -> Gemini:
    return Gemini(
        model=_cfg.model_name, retry_options=types.HttpRetryOptions(attempts=3)
    )


# TODO(jornada): renomear para o papel da jornada escolhida.
analyst = Agent(
    name="analyst",
    model=_model(),
    instruction=load_prompt("analyst"),
    tools=[
        get_customer_profile,
        get_transactions,
        get_card_summary,
        get_goals,
        get_account_summary,
        compound_interest,
        compare_revolving_vs_installments,
        time_to_reach_goal,
        PROPOSE_ACTION_TOOL,
    ],
)

# TODO(jornada): renomear para o papel da jornada escolhida.
educator = Agent(
    name="educator",
    model=_model(),
    instruction=load_prompt("educator"),
    tools=[search_knowledge],
)

root_agent = Agent(
    # Mantenha em sincronia com agents-cli-manifest.yaml.
    name="orchestrator",
    model=_model(),
    instruction=load_prompt("orchestrator"),
    sub_agents=[analyst, educator],
    tools=[give_consent, remember_preference, recall_profile, forget_me],
    before_agent_callback=seed_demo_identity,
)

app = App(
    name="app",
    root_agent=root_agent,
    plugins=[SecurityPlugin(), AuditPlugin()],
    # compaction_interval e overlap_size precisam ser definidos juntos (ADK 2.8).
    # overlap preserva contexto entre janelas compactadas.
    events_compaction_config=EventsCompactionConfig(
        compaction_interval=10, overlap_size=3
    ),
)
