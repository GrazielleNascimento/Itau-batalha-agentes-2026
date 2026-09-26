"""Autorização na fronteira da tool.

Defesa em profundidade da D2: as tools já leem o customer_id do estado, mas uma
tool escrita às pressas no sábado pode expor o parâmetro de novo.
"""

from __future__ import annotations

from app.callbacks.pii import CPF_RE, cpf_valido, so_digitos

# Substring, não igualdade: quem escreve uma tool às pressas escreve
# "customerId", "user_id" ou "cpf_do_cliente", e nenhum deles bate por igualdade.
FORBIDDEN_FRAGMENTS = ("customer", "cpf", "client", "account", "user_id", "userid")


class UnsafeToolArgs(ValueError):
    """A chamada trouxe um identificador que deveria vir da sessão."""


def _normaliza(chave: str) -> str:
    return chave.lower().replace("_", "").replace("-", "")


def _verificar(tool_name: str, valor: object, chave: str | None = None) -> None:
    """Desce em dict e list: um identificador aninhado é o caso mais provável."""
    if chave is not None:
        plana = _normaliza(chave)
        for fragmento in FORBIDDEN_FRAGMENTS:
            if _normaliza(fragmento) in plana:
                raise UnsafeToolArgs(
                    f"{tool_name}: o argumento {chave!r} é proibido; "
                    "a identidade vem do estado da sessão."
                )
    if isinstance(valor, dict):
        for k, v in valor.items():
            _verificar(tool_name, v, k)
    elif isinstance(valor, (list, tuple)):
        for v in valor:
            _verificar(tool_name, v, None)
    elif isinstance(valor, str):
        for m in CPF_RE.finditer(valor):
            if cpf_valido(so_digitos(m.group())):
                raise UnsafeToolArgs(f"{tool_name}: CPF em argumento de tool.")


def assert_tool_args_safe(tool_name: str, args: dict) -> None:
    for chave, valor in args.items():
        _verificar(tool_name, valor, chave)
