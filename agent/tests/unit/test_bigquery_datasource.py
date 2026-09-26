"""Testa a BigQueryDataSource sem BigQuery: cliente falso que registra a query."""

import pytest

from app.datasources.bigquery import BigQueryDataSource


class FakeJob:
    def __init__(self, linhas):
        self._linhas = linhas

    def result(self):
        return iter(self._linhas)


class FakeClient:
    """Registra query e parâmetros; devolve as linhas que mandarmos."""

    def __init__(self, linhas=()):
        self.linhas = list(linhas)
        self.queries: list[str] = []
        self.parametros: list[list] = []

    def query(self, sql, job_config=None):
        self.queries.append(sql)
        self.parametros.append(list(getattr(job_config, "query_parameters", []) or []))
        return FakeJob(self.linhas)


CLIENTE_BRUTO = {
    "customer_id": "FICT-0001",
    "cpf": "529.982.247-25",
    "full_name": "Fulano de Tal da Silva",
    "first_name": "Fulano",
    "age_band": "28-50",
    "income_band": "2k-3k",
    "suitability": "conservador",
    "preferred_channel": "app",
    "accessibility_flags": "",
}


def test_identificador_vai_como_parametro_e_nao_concatenado():
    """SQL injection: o customer_id nunca pode entrar no texto da query."""
    c = FakeClient([CLIENTE_BRUTO])
    BigQueryDataSource(client=c, project="p", dataset="d").get_customer("FICT-0001")
    assert "FICT-0001" not in c.queries[0], c.queries[0]
    assert "@customer_id" in c.queries[0]
    valores = [p.value for p in c.parametros[0]]
    assert "FICT-0001" in valores


def test_aspas_no_identificador_nao_quebram_a_query():
    c = FakeClient([])
    malicioso = "FICT-0001' OR '1'='1"
    BigQueryDataSource(client=c, project="p", dataset="d").get_customer(malicioso)
    assert "OR '1'='1" not in c.queries[0]


def test_projecao_minima_vale_tambem_no_bigquery():
    """D8: CPF e nome completo não podem sair, venham de onde vierem."""
    c = FakeClient([CLIENTE_BRUTO])
    perfil = BigQueryDataSource(client=c, project="p", dataset="d").get_customer("FICT-0001")
    assert "cpf" not in perfil
    assert "full_name" not in perfil
    assert perfil["customer_id"] == "FICT-0001"


def test_cliente_inexistente_devolve_none():
    c = FakeClient([])
    assert BigQueryDataSource(client=c, project="p", dataset="d").get_customer("X") is None


def test_transacoes_filtram_por_periodo_e_categoria():
    linhas = [{"date": "2026-08-01", "category": "mercado", "amount": -50.0, "description": "x"}]
    c = FakeClient(linhas)
    ds = BigQueryDataSource(client=c, project="p", dataset="d")
    ds.get_transactions("FICT-0001", "2026-01-01", "2026-12-31", "mercado")
    nomes = {p.name for p in c.parametros[0]}
    assert {"customer_id", "inicio", "fim", "category"} <= nomes


def test_datas_invertidas_sao_normalizadas():
    c = FakeClient([])
    ds = BigQueryDataSource(client=c, project="p", dataset="d")
    ds.get_transactions("FICT-0001", "2026-12-31", "2026-01-01")
    params = {p.name: p.value for p in c.parametros[0]}
    assert params["inicio"] <= params["fim"]


def test_fabrica_devolve_bigquery_quando_configurado(monkeypatch):
    monkeypatch.setenv("DATA_SOURCE", "bigquery")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "proj")
    import app.datasources.bigquery as mod
    from app.datasources.factory import get_data_source

    monkeypatch.setattr(mod, "_client_padrao", lambda: FakeClient([]))
    ds = get_data_source()
    assert isinstance(ds, BigQueryDataSource)


def test_fabrica_exige_projeto(monkeypatch):
    monkeypatch.setenv("DATA_SOURCE", "bigquery")
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    from app.datasources.factory import get_data_source

    with pytest.raises(ValueError, match="GOOGLE_CLOUD_PROJECT"):
        get_data_source()
