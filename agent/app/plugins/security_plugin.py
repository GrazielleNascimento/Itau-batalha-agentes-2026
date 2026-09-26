"""Guardrails transversais.

Registrado uma vez em App(plugins=[...]), vale para o orquestrador e para todo
subagente — inclusive os que forem criados no sábado. Um callback por agente
faria a cobertura depender de alguém lembrar de plugá-lo.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.plugins.base_plugin import BasePlugin
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext
from google.genai import types

from app.callbacks.authz import UnsafeToolArgs, assert_tool_args_safe
from app.callbacks.injection import detect_injection
from app.callbacks.output import check_output
from app.callbacks.pii import mask_pii
from app.config import load_config

RECUSA = (
    "Não consigo atender esse pedido. Posso ajudar com a sua situação financeira "
    "ou explicar um conceito. Se preferir, posso transferir para um atendente."
)
TRANSFERENCIA = "Vou transferir você para um atendente humano, que consegue ajudar melhor a partir daqui."
# Campos de texto livre vindos dos dados: escritos por terceiros, nunca confiáveis.
FREE_TEXT_KEYS = {"description", "name", "merchant", "title", "excerpt"}
SANITIZED = "[conteúdo removido: instrução suspeita nos dados]"


# O PluginManager faz early exit no primeiro retorno não-None: quando o
# SecurityPlugin age, o AuditPlugin NUNCA roda. Por isso o guard emite a própria
# linha de auditoria, em vez de depender do plugin seguinte.
_audit_logger = logging.getLogger("audit")


def _audit_guard(guard: str, **campos: Any) -> None:
    """Registra que um guard agiu. Nunca o conteúdo, só o metadado."""
    _audit_logger.info(
        json.dumps({"event": "guard", "guard": guard, **campos}, ensure_ascii=False)
    )


def _texto_resposta(texto: str) -> LlmResponse:
    return LlmResponse(
        content=types.Content(role="model", parts=[types.Part(text=texto)])
    )


def _limpar(valor: Any, chave: str | None = None) -> tuple[Any, bool]:
    """Percorre o resultado da tool e neutraliza injection em campos de texto livre."""
    if isinstance(valor, dict):
        saida, mexeu = {}, False
        for k, v in valor.items():
            saida[k], m = _limpar(v, k)
            mexeu = mexeu or m
        return saida, mexeu
    if isinstance(valor, list):
        itens = [_limpar(v, chave) for v in valor]
        return [i for i, _ in itens], any(m for _, m in itens)
    if (
        isinstance(valor, str)
        and chave in FREE_TEXT_KEYS
        and detect_injection(valor).blocked
    ):
        return SANITIZED, True
    return valor, False


class SecurityPlugin(BasePlugin):
    def __init__(self) -> None:
        super().__init__(name="security")
        # Sob streaming, after_model roda por chunk. Acumulamos por invocação
        # para enxergar PII partida entre dois chunks.
        self._acumulado: dict[str, str] = {}

    async def before_model_callback(
        self, *, callback_context: CallbackContext, llm_request: LlmRequest
    ) -> LlmResponse | None:
        cfg = load_config()
        estado = callback_context.state
        conteudos = llm_request.contents or []

        # Mascaramento PRIMEIRO. Além de ser idempotente, isto é o que garante
        # residência: com Model Armor ligado o texto sai do Brasil, e o que
        # atravessa a fronteira já vai sem CPF, cartão, e-mail e telefone.
        for content in conteudos:
            for part in content.parts or []:
                if not part.text:
                    continue
                mascarado, achados = mask_pii(part.text)
                if achados:
                    part.text = mascarado
                    _audit_guard("pii_masked", kinds=achados)

        # Injeção: só na mensagem NOVA. O histórico já foi vetado, e a mensagem
        # bloqueada continua persistida na sessão — varrer tudo a redetectava a
        # cada turno, recusando conversa legítima para sempre e somando strike.
        for part in (conteudos[-1].parts if conteudos else None) or []:
            if not part.text:
                continue
            motivo = None
            if detect_injection(part.text).blocked:
                motivo = "prompt_injection"
            elif cfg.use_model_armor:
                # Camada adicional, nunca substituta: medimos que ela pega
                # paráfrases que o heurístico perde, e que ambas erram juntas
                # num jailbreak estilo DAN.
                from app.callbacks import model_armor

                veredito = model_armor.scan_prompt(part.text)
                if veredito.unavailable:
                    _audit_guard("model_armor_unavailable")
                elif veredito.blocked:
                    motivo = "model_armor"
            if motivo:
                strikes = estado.get("guard_strikes", 0) + 1
                estado["guard_strikes"] = strikes
                _audit_guard(motivo, strikes=strikes)
                if strikes >= cfg.guard_strikes_to_human:
                    return _texto_resposta(TRANSFERENCIA)
                return _texto_resposta(RECUSA)
        return None

    async def before_tool_callback(
        self, *, tool: BaseTool, tool_args: dict[str, Any], tool_context: ToolContext
    ) -> dict[str, Any] | None:
        try:
            assert_tool_args_safe(tool.name, tool_args)
        except UnsafeToolArgs as erro:
            _audit_guard("unsafe_tool_args", tool=tool.name)
            return {"error": str(erro)}
        return None

    async def after_tool_callback(
        self,
        *,
        tool: BaseTool,
        tool_args: dict[str, Any],
        tool_context: ToolContext,
        result: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Injection indireta: neutraliza texto de terceiro vindo dos dados."""
        limpo, mexeu = _limpar(result)
        if mexeu:
            _audit_guard("indirect_injection", tool=tool.name)
            return limpo
        return None

    async def after_model_callback(
        self, *, callback_context: CallbackContext, llm_response: LlmResponse
    ) -> LlmResponse | None:
        cfg = load_config()
        suitability = callback_context.state.get("suitability", "moderado")
        inv = getattr(callback_context, "invocation_id", "sem-invocacao")
        partes = (llm_response.content.parts if llm_response.content else None) or []
        final = not getattr(llm_response, "partial", False)
        self._acumulado[inv] = self._acumulado.get(inv, "") + "".join(
            p.text for p in partes if p.text
        )

        # Cada chunk é checado isoladamente: o que couber inteiro num chunk é
        # mascarado ANTES de sair.
        for part in partes:
            if not part.text:
                continue
            texto, violacoes = check_output(part.text, suitability)
            if violacoes:
                _audit_guard("output_violation", kinds=violacoes)
                if final:
                    self._acumulado.pop(inv, None)
                return _texto_resposta(texto if "pii_leak" in violacoes else RECUSA)

        if final:
            completo = self._acumulado.pop(inv, "")
            _, violacoes = check_output(completo, suitability)
            if violacoes:
                # Chegou aqui = a PII estava partida entre chunks, e os chunks
                # anteriores JÁ foram entregues. Não dá para desfazer; registra
                # para a trilha de auditoria. Mitigação real: desligar streaming.
                _audit_guard("split_pii_leak", kinds=violacoes)
            # Model Armor na SAÍDA: com os filtros de IA responsável no template,
            # olhar só o prompt deixaria o agente produzir o que o filtro barra.
            # Roda no texto completo, uma vez por invocação, não por chunk.
            if cfg.use_model_armor and completo:
                from app.callbacks import model_armor

                veredito = model_armor.scan_response(completo)
                if veredito.unavailable:
                    _audit_guard("model_armor_unavailable", where="response")
                elif veredito.blocked:
                    _audit_guard("model_armor_response", kinds=["rai_or_sdp"])
                    return _texto_resposta(RECUSA)
        return None
