"""Matemática financeira. Fica em código, nunca no LLM.

São três tools e não uma calculadora polimórfica porque o modelo escolhe tool
lendo docstring, e uma função com parâmetro `mode` descreve três comportamentos
numa docstring só.
"""

from __future__ import annotations

import math

MAX_MONTHS = 1200  # 100 anos: teto de segurança do laço


def _faixa_invalida(nome: str, valor: int) -> dict | None:
    """Os parâmetros vêm do texto do usuário via LLM. Fora da faixa, devolvemos
    error estruturado em vez de número inventado ou laço que trava o playground."""
    if valor < 1 or valor > MAX_MONTHS:
        return {"error": f"{nome} deve estar entre 1 e {MAX_MONTHS}; recebido {valor}."}
    return None


def compound_interest(
    principal: float, monthly_rate: float, months: int, monthly_contribution: float
) -> dict:
    """Projeta um valor com juros compostos e aportes mensais.

    Args:
        principal: valor inicial em reais.
        monthly_rate: taxa mensal em decimal (0.01 = 1% ao mês).
        months: número de meses.
        monthly_contribution: aporte no fim de cada mês, em reais.

    Returns:
        final_amount, total_contributed e interest_earned.
    """
    if erro := _faixa_invalida("months", months):
        return erro
    saldo = principal
    for _ in range(months):
        saldo = saldo * (1 + monthly_rate) + monthly_contribution
    aportado = principal + monthly_contribution * months
    return {
        "final_amount": round(saldo, 2),
        "total_contributed": round(aportado, 2),
        "interest_earned": round(saldo - aportado, 2),
    }


def compare_revolving_vs_installments(
    balance: float, revolving_rate: float, installment_rate: float, n_installments: int
) -> dict:
    """Compara o custo de rolar a fatura no rotativo com o de parcelar.

    Args:
        balance: valor devido em reais.
        revolving_rate: taxa mensal do rotativo em decimal (0.15 = 15% ao mês).
        installment_rate: taxa mensal do parcelamento em decimal.
        n_installments: número de parcelas a comparar.

    Returns:
        revolving_total, installments_total, installment_value, savings e cheaper.
    """
    if erro := _faixa_invalida("n_installments", n_installments):
        return erro
    rotativo = balance * (1 + revolving_rate) ** n_installments
    if installment_rate == 0:
        parcela = balance / n_installments
    else:
        i = installment_rate
        parcela = balance * i / (1 - (1 + i) ** -n_installments)
    parcelado = parcela * n_installments
    return {
        "revolving_total": round(rotativo, 2),
        "installments_total": round(parcelado, 2),
        "installment_value": round(parcela, 2),
        "savings": round(rotativo - parcelado, 2),
        "cheaper": "installments" if parcelado < rotativo else "revolving",
    }


def time_to_reach_goal(
    target: float, current: float, monthly_saving: float, monthly_rate: float
) -> dict:
    """Calcula em quantos meses uma meta financeira é atingida.

    Args:
        target: valor alvo em reais.
        current: valor já guardado em reais.
        monthly_saving: quanto a pessoa consegue guardar por mês, em reais.
        monthly_rate: rendimento mensal em decimal (0.0 se o dinheiro não rende).

    Returns:
        months (None se inalcançável), reachable e reason.
    """
    if current >= target:
        return {"months": 0, "reachable": True, "reason": None}
    if monthly_saving <= 0:
        return {
            "months": None,
            "reachable": False,
            "reason": "sem aporte mensal a meta não é atingida",
        }
    if monthly_rate == 0:
        return {
            "months": math.ceil((target - current) / monthly_saving),
            "reachable": True,
            "reason": None,
        }
    saldo, meses = current, 0
    while saldo < target and meses < MAX_MONTHS:
        saldo = saldo * (1 + monthly_rate) + monthly_saving
        meses += 1
    if saldo < target:
        return {"months": None, "reachable": False, "reason": "mais de 100 anos"}
    return {"months": meses, "reachable": True, "reason": None}
