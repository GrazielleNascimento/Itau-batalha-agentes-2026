import re
from types import SimpleNamespace

from google.adk.sessions.state import State

from google.adk.tools.function_tool import FunctionTool

from app.tools import customer

CPF_EM_QUALQUER_LUGAR = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")


def ctx(customer_id="FICT-0001"):
    valores = {"customer_id": customer_id} if customer_id else {}
    return SimpleNamespace(state=State(value=valores, delta={}))


def test_usa_o_id_da_sessao_e_ignora_o_texto_do_usuario():
    # O usuário pediu "o extrato do cliente 42"; a sessão é do FICT-0001.
    r = customer.get_customer_profile(tool_context=ctx("FICT-0001"))
    assert r["profile"]["customer_id"] == "FICT-0001"


def test_sem_identidade_na_sessao_recusa():
    r = customer.get_customer_profile(tool_context=ctx(None))
    assert r["error"]
    assert "profile" not in r


def test_customer_id_nao_e_exposto_ao_modelo():
    for fn in (
        customer.get_customer_profile,
        customer.get_transactions,
        customer.get_card_summary,
    ):
        schema = FunctionTool(fn)._get_declaration().parameters_json_schema or {}
        expostos = set((schema.get("properties") or {}).keys())
        assert "customer_id" not in expostos, fn.__name__
        assert "tool_context" not in expostos, fn.__name__


def test_get_transactions_expoe_apenas_periodo_e_categoria():
    schema = FunctionTool(customer.get_transactions)._get_declaration().parameters_json_schema
    assert set(schema["properties"]) == {"start_date", "end_date", "category"}


def test_nenhuma_tool_devolve_cpf():
    for r in (
        customer.get_customer_profile(tool_context=ctx()),
        customer.get_transactions("2026-01-01", "2026-12-31", tool_context=ctx()),
        customer.get_card_summary(tool_context=ctx()),
    ):
        assert not CPF_EM_QUALQUER_LUGAR.search(repr(r)), r


def test_cliente_inexistente_nao_inventa():
    r = customer.get_customer_profile(tool_context=ctx("FICT-9999"))
    assert r["error"]


def test_expoe_metas_e_saldo_para_alimentar_as_calculadoras():
    """I1: sem estas tools o analyst tem time_to_reach_goal e nenhuma fonte para
    target/current/monthly_saving — preenche de cabeça e a calculadora dá
    autoridade de cálculo a um número inventado."""
    metas = customer.get_goals(tool_context=ctx())
    assert metas["goals"], metas
    assert {"goal_id", "name", "target_amount", "current_amount"} <= set(metas["goals"][0])

    conta = customer.get_account_summary(tool_context=ctx())
    assert "balance" in conta["account"]
    assert "overdraft_limit" in conta["account"]


def test_metas_e_saldo_tambem_usam_o_id_da_sessao():
    for fn in (customer.get_goals, customer.get_account_summary):
        schema = FunctionTool(fn)._get_declaration().parameters_json_schema or {}
        assert not (schema.get("properties") or {}), fn.__name__
        assert fn(tool_context=ctx(None))["error"]


def test_separa_entrada_de_saida_em_vez_de_somar_tudo():
    """I9: 'quanto gastei?' somava salário com gasto e devolvia o líquido —
    para o arquétipo organizado, um número positivo apresentado como gasto."""
    r = customer.get_transactions("2026-01-01", "2026-12-31", tool_context=ctx())
    assert r["total_out"] > 0, "saída é positiva e absoluta"
    assert r["total_in"] > 0
    assert round(r["net"], 2) == round(r["total_in"] - r["total_out"], 2)


def test_data_em_formato_invalido_nao_vira_zero_silencioso():
    """I9: '2026-7-01' invertia o intervalo na comparação de string e devolvia
    zero transações — 'você não gastou nada com mercado'."""
    r = customer.get_transactions("2026-7-01", "2026-12-31", tool_context=ctx())
    assert r["error"]
    assert "AAAA-MM-DD" in r["error"]
