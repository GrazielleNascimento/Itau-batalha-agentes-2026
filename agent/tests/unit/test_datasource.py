import pytest

from app.datasources.factory import get_data_source
from app.datasources.local import MissingDataError


def test_le_cliente_existente():
    ds = get_data_source()
    c = ds.get_customer("FICT-0001")
    assert c is not None
    assert c["customer_id"] == "FICT-0001"


def test_cliente_inexistente_devolve_none():
    assert get_data_source().get_customer("FICT-9999") is None


def test_filtra_por_periodo_e_categoria():
    ds = get_data_source()
    todas = ds.get_transactions("FICT-0001", "2026-01-01", "2026-12-31")
    mercado = ds.get_transactions("FICT-0001", "2026-01-01", "2026-12-31", "mercado")
    assert todas and mercado
    assert len(mercado) < len(todas)
    assert {t["category"] for t in mercado} == {"mercado"}


def test_datas_invertidas_nao_devolvem_vazio():
    ds = get_data_source()
    normal = ds.get_transactions("FICT-0001", "2026-01-01", "2026-12-31")
    invertido = ds.get_transactions("FICT-0001", "2026-12-31", "2026-01-01")
    assert len(invertido) == len(normal)


def test_projecao_nao_expoe_nome_completo_nem_cpf():
    c = get_data_source().get_customer("FICT-0001")
    assert "cpf" not in c
    assert "full_name" not in c
    assert set(c) == {
        "customer_id", "first_name", "age_band", "income_band",
        "suitability", "preferred_channel", "accessibility_flags",
    }


def test_data_source_desconhecido_falha_com_mensagem_util(monkeypatch):
    """A D4 (NotImplementedError para bigquery) foi superada: a fonte existe.
    O que continua valendo é recusar um modo que ninguém implementou."""
    monkeypatch.setenv("DATA_SOURCE", "cassete")
    with pytest.raises(ValueError, match="cassete"):
        get_data_source()


def test_csv_ausente_diz_para_rodar_make_data(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from app.datasources import local

    local.LocalDataSource._carregar.cache_clear()
    with pytest.raises(MissingDataError, match="make data"):
        get_data_source().get_customer("FICT-0001")
    local.LocalDataSource._carregar.cache_clear()


def test_projecao_descarta_cpf_e_nome_que_existem_na_origem(monkeypatch):
    """I10: a origem tem cpf e full_name; a projeção tem de removê-los de verdade."""
    import csv
    from pathlib import Path

    from app.config import load_config

    bruto = Path(load_config().data_dir) / "synthetic" / "customers.csv"
    with open(bruto, encoding="utf-8") as fh:
        origem = next(r for r in csv.DictReader(fh) if r["customer_id"] == "FICT-0001")
    assert origem["cpf"] and origem["full_name"]

    projetado = get_data_source().get_customer("FICT-0001")
    assert "cpf" not in projetado
    assert "full_name" not in projetado
    assert origem["cpf"] not in repr(projetado)
    assert origem["full_name"] not in repr(projetado)
