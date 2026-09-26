"""Ações que mudam algo exigem um 'sim' explícito do cliente.

require_confirmation está marcada como experimental no ADK 2.8. Se quebrar numa
atualização, o plano B é um passo de confirmação no prompt do orquestrador —
mais fraco, porque depende de o modelo obedecer.
"""

from __future__ import annotations

from google.adk.tools.function_tool import FunctionTool
from google.adk.tools.tool_context import ToolContext

# Só para teste: registra o que de fato executou.
EXECUTED: list[str] = []


def propose_action(action_type: str, details: str, tool_context: ToolContext) -> dict:
    """Propõe uma ação financeira ao cliente. Só executa após confirmação explícita.

    Args:
        action_type: tipo da ação, por exemplo "transfer", "pay_invoice" ou "set_goal".
        details: descrição curta do que será feito, em linguagem simples.

    Returns:
        status e a ação registrada.
    """
    # TODO(jornada): trocar pelo efeito real da ação da jornada escolhida.
    EXECUTED.append(action_type)
    return {"status": "executed", "action_type": action_type, "details": details}


PROPOSE_ACTION_TOOL = FunctionTool(propose_action, require_confirmation=True)
