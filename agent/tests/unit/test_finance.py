from app.tools.finance import (
    compare_revolving_vs_installments,
    compound_interest,
    time_to_reach_goal,
)


def test_juros_compostos_sem_aporte():
    # 1000 a 1% por 12 meses = 1000 * 1.01^12 = 1126.83
    r = compound_interest(1000.0, 0.01, 12, 0.0)
    assert round(r["final_amount"], 2) == 1126.83
    assert round(r["interest_earned"], 2) == 126.83


def test_juros_compostos_com_aporte():
    # Anuidade ordinária: 100 * ((1.01^12 - 1)/0.01) = 1268.25 (fórmula fechada).
    r = compound_interest(0.0, 0.01, 12, 100.0)
    assert round(r["final_amount"], 2) == 1268.25
    assert round(r["total_contributed"], 2) == 1200.0


def test_juros_compostos_taxa_zero():
    r = compound_interest(500.0, 0.0, 10, 50.0)
    assert r["final_amount"] == 1000.0
    assert r["interest_earned"] == 0.0


def test_rotativo_custa_mais_que_parcelamento():
    r = compare_revolving_vs_installments(1000.0, 0.15, 0.03, 12)
    assert r["revolving_total"] > r["installments_total"]
    assert r["cheaper"] == "installments"


def test_meta_com_taxa_zero():
    r = time_to_reach_goal(10000.0, 0.0, 500.0, 0.0)
    assert r["months"] == 20
    assert r["reachable"] is True


def test_meta_com_juros_chega_mais_cedo():
    assert time_to_reach_goal(10000.0, 0.0, 500.0, 0.01)["months"] == 19


def test_meta_ja_atingida():
    r = time_to_reach_goal(100.0, 200.0, 50.0, 0.01)
    assert r["months"] == 0


def test_meta_sem_aporte_e_inalcancavel_e_nao_trava():
    # Review Focus 1: monthly_saving <= 0 nunca chega ao alvo.
    for aporte in (0.0, -10.0):
        r = time_to_reach_goal(10000.0, 0.0, aporte, 0.01)
        assert r["reachable"] is False
        assert r["months"] is None
        assert r["reason"]


def test_entradas_invalidas_devolvem_erro_em_vez_de_numero_inventado():
    """I6: n_installments=0 é o que o modelo passa em 'e se eu pagar à vista?'.
    Meses negativos devolviam R$500 de juros a partir de entrada inválida."""
    assert compare_revolving_vs_installments(1000.0, 0.15, 0.03, 0)["error"]
    assert compare_revolving_vs_installments(1000.0, 0.15, 0.03, -3)["error"]
    assert compound_interest(1000.0, 0.01, -5, 100.0)["error"]
    assert compound_interest(1000.0, 0.01, 0, 100.0)["error"]


def test_laco_tem_teto_e_nao_trava_o_playground():
    # months vem do texto do usuário via LLM; sem teto o laço síncrono
    # bloqueia o event loop.
    assert compound_interest(1000.0, 0.01, 50_000_000, 0.0)["error"]
