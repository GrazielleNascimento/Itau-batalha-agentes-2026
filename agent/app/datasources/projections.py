"""Minimização de dados (LGPD): o único lugar que decide o que sai da camada de dados.

Nada aqui pode devolver CPF, nome completo ou qualquer identificador direto além
do customer_id pseudonimizado. O teste test_nenhuma_tool_devolve_cpf depende disso.
"""

from __future__ import annotations

CUSTOMER_FIELDS = (
    "customer_id",
    "first_name",
    "age_band",
    "income_band",
    "suitability",
    "preferred_channel",
    "accessibility_flags",
)
TRANSACTION_FIELDS = ("date", "category", "amount", "description")
CARD_FIELDS = (
    "credit_limit",
    "current_invoice",
    "minimum_payment",
    "revolving_balance",
    "installment_count",
)
GOAL_FIELDS = ("goal_id", "name", "target_amount", "current_amount")


def _pick(row: dict, campos: tuple[str, ...]) -> dict:
    return {c: row[c] for c in campos if c in row}


def project_customer(row: dict) -> dict:
    return _pick(row, CUSTOMER_FIELDS)


def project_transaction(row: dict) -> dict:
    d = _pick(row, TRANSACTION_FIELDS)
    if "amount" in d:
        d["amount"] = float(d["amount"])
    return d


def project_card(row: dict) -> dict:
    return {c: float(row[c]) for c in CARD_FIELDS if c in row}


def project_goal(row: dict) -> dict:
    d = _pick(row, GOAL_FIELDS)
    for c in ("target_amount", "current_amount"):
        if c in d:
            d[c] = float(d[c])
    return d
