"""Checagem da resposta antes de chegar ao cliente."""

from __future__ import annotations

import re

from app.callbacks.pii import mask_pii

RISCO_ALTO = re.compile(
    r"\b(cripto|criptomoedas?|bitcoin|day\s?trade|alavancagem|derivativos?|op(c|ç)(o|õ)es)\b",
    re.IGNORECASE,
)
PERFIS_INCOMPATIVEIS = {"conservador"}


def check_output(text: str, suitability: str) -> tuple[str, list[str]]:
    """Devolve o texto (com PII mascarada) e a lista de violações encontradas."""
    violacoes: list[str] = []
    texto, achados = mask_pii(text)
    if achados:
        violacoes.append("pii_leak")
    if suitability in PERFIS_INCOMPATIVEIS and RISCO_ALTO.search(text):
        violacoes.append("suitability_mismatch")
    return texto, violacoes
