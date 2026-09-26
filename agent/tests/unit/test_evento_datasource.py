"""EventoDataSource: o extrato_sintetico do hackathon atrás do mesmo Protocol.
Testado com linhas de fixture, não com o snapshot real (que não é versionado)."""

import pytest

from app.datasources.evento import EventoDataSource, normalizar_categoria

U = "00108ccd-699c-453a-a9f9-a66aad6e03e5"
LINHAS = [
    # id_usuario, data, tipo, descr, vlr, macro, micro, saldo_apos, parcela_atual, parcela_total
    dict(id_usuario=U, data="2025-01-02", tipo="S", descr="pix qrs padaria vila", vlr="121.43",
         nom_cate_macro="Restaurantes", nom_cate_micro="Padaria", saldo_apos="1962.80", parcela_atual="", parcela_total=""),
    dict(id_usuario=U, data="2025-01-05", tipo="S", descr="mercado bom preco", vlr="310.00",
         nom_cate_macro="Mercado", nom_cate_micro="Supermercado", saldo_apos="1652.80", parcela_atual="", parcela_total=""),
    dict(id_usuario=U, data="2025-01-10", tipo="E", descr="salario empresa x", vlr="5200.00",
         nom_cate_macro="Salarios e bonificacoes", nom_cate_micro="Salario", saldo_apos="6852.80", parcela_atual="", parcela_total=""),
    dict(id_usuario=U, data="2025-01-15", tipo="S", descr="loja tv 55 3/10", vlr="250.00",
         nom_cate_macro="Lojas e sites", nom_cate_micro="Eletronicos", saldo_apos="6602.80", parcela_atual="3", parcela_total="10"),
    dict(id_usuario=U, data="2025-02-03", tipo="S", descr="mercado bom preco", vlr="290.00",
         nom_cate_macro="Mercado", nom_cate_micro="Supermercado", saldo_apos="6312.80", parcela_atual="", parcela_total=""),
    dict(id_usuario="outro-usuario", data="2025-01-05", tipo="S", descr="mercado", vlr="99.00",
         nom_cate_macro="Mercado", nom_cate_micro="Supermercado", saldo_apos="10.00", parcela_atual="", parcela_total=""),
]


@pytest.fixture
def ds():
    return EventoDataSource(LINHAS)


def test_normaliza_categoria_para_o_vocabulario_do_agente():
    assert normalizar_categoria("Mercado") == "mercado"
    assert normalizar_categoria("Salarios e bonificacoes") == "salario"
    assert normalizar_categoria("Restaurantes") == "restaurantes"


def test_saida_e_negativa_entrada_e_positiva(ds):
    ts = ds.get_transactions(U, "2025-01-01", "2025-01-31")
    por_desc = {t["description"]: t["amount"] for t in ts}
    assert por_desc["pix qrs padaria vila"] == -121.43
    assert por_desc["salario empresa x"] == 5200.0


def test_filtra_por_periodo_e_categoria(ds):
    jan = ds.get_transactions(U, "2025-01-01", "2025-01-31", "mercado")
    assert [t["amount"] for t in jan] == [-310.0]
    tudo = ds.get_transactions(U, "2025-01-01", "2025-12-31", "mercado")
    assert len(tudo) == 2


def test_nunca_vaza_outro_usuario(ds):
    ts = ds.get_transactions(U, "2025-01-01", "2025-12-31")
    assert all("outro" not in t["description"] for t in ts)
    assert ds.get_customer("outro-usuario")["customer_id"] == "outro-usuario"


def test_datas_invertidas_sao_normalizadas(ds):
    assert len(ds.get_transactions(U, "2025-12-31", "2025-01-01")) == 5


def test_perfil_minimo_sem_pii_e_com_renda_derivada(ds):
    p = ds.get_customer(U)
    assert set(p) <= {"customer_id", "first_name", "age_band", "income_band",
                      "suitability", "preferred_channel", "accessibility_flags"}
    assert p["customer_id"] == U
    assert p["income_band"] == "5k-6k"  # derivada do salário de jan
    assert p["suitability"] == "nao_informado"  # o dado do evento não tem; não inventar


def test_conta_e_o_saldo_mais_recente(ds):
    assert ds.get_accounts(U) == {"balance": 6312.80, "overdraft_limit": 0.0}


def test_cartao_deriva_parcelas_do_extrato(ds):
    c = ds.get_card(U)
    assert c["installment_count"] == 1.0
    assert "credit_limit" not in c  # não existe no dado; não inventar


def test_cliente_inexistente_devolve_none_ou_vazio(ds):
    assert ds.get_customer("nao-existe") is None
    assert ds.get_accounts("nao-existe") is None
    assert ds.get_goals("nao-existe") == []


def test_fabrica_evento_exige_snapshot(monkeypatch, tmp_path):
    from app.datasources.factory import get_data_source

    monkeypatch.setenv("DATA_SOURCE", "evento")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    with pytest.raises(FileNotFoundError, match="stage-evento"):
        get_data_source()


def test_fabrica_evento_carrega_o_snapshot(monkeypatch, tmp_path):
    import csv

    from app.datasources.factory import get_data_source

    (tmp_path / "evento").mkdir()
    with open(tmp_path / "evento" / "extrato.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(LINHAS[0]))
        w.writeheader()
        w.writerows(LINHAS)
    monkeypatch.setenv("DATA_SOURCE", "evento")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from app.datasources import evento as mod

    mod._carregar_snapshot.cache_clear()
    ds = get_data_source()
    assert isinstance(ds, EventoDataSource)
    assert ds.get_customer(U) is not None
