"""Fonte de dados em BigQuery.

Mesmo contrato da LocalDataSource: as tools não mudam ao trocar de fonte.

Toda consulta é parametrizada. O `customer_id` vem do estado da sessão, mas
concatená-lo no texto da query recriaria por SQL o buraco que a D2 fechou no
prompt — um identificador com aspas viraria injeção.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from google.cloud import bigquery

from app.datasources.projections import (
    project_card,
    project_customer,
    project_goal,
    project_transaction,
)


@lru_cache(maxsize=1)
def _client_padrao() -> bigquery.Client:
    return bigquery.Client()


def _config(**parametros: Any) -> bigquery.QueryJobConfig:
    tipos = {str: "STRING", int: "INT64", float: "FLOAT64"}
    return bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter(nome, tipos[type(valor)], valor)
            for nome, valor in parametros.items()
        ]
    )


class BigQueryDataSource:
    def __init__(
        self,
        client: Any | None = None,
        project: str | None = None,
        dataset: str = "batalha_agentes",
    ) -> None:
        self._client = client if client is not None else _client_padrao()
        self._project = project or os.environ["GOOGLE_CLOUD_PROJECT"]
        self._dataset = dataset

    def _tabela(self, nome: str) -> str:
        return f"`{self._project}.{self._dataset}.{nome}`"

    def _linhas(self, sql: str, **parametros: Any) -> list[dict]:
        job = self._client.query(sql, job_config=_config(**parametros))
        return [dict(linha) for linha in job.result()]

    def _um(self, sql: str, **parametros: Any) -> dict | None:
        linhas = self._linhas(sql, **parametros)
        return linhas[0] if linhas else None

    def get_customer(self, customer_id: str) -> dict | None:
        linha = self._um(
            f"SELECT * FROM {self._tabela('customers')} WHERE customer_id = @customer_id LIMIT 1",
            customer_id=customer_id,
        )
        return project_customer(linha) if linha else None

    def get_accounts(self, customer_id: str) -> dict | None:
        linha = self._um(
            f"SELECT balance, overdraft_limit FROM {self._tabela('accounts')} "
            "WHERE customer_id = @customer_id LIMIT 1",
            customer_id=customer_id,
        )
        if linha is None:
            return None
        return {
            "balance": float(linha["balance"]),
            "overdraft_limit": float(linha["overdraft_limit"]),
        }

    def get_transactions(
        self,
        customer_id: str,
        start_date: str,
        end_date: str,
        category: str | None = None,
    ) -> list[dict]:
        # Datas invertidas não podem virar resultado vazio silencioso.
        inicio, fim = sorted((start_date, end_date))
        filtro_categoria = " AND category = @category" if category else ""
        parametros: dict[str, Any] = {
            "customer_id": customer_id,
            "inicio": inicio,
            "fim": fim,
        }
        if category:
            parametros["category"] = category
        linhas = self._linhas(
            f"SELECT date, category, amount, description FROM {self._tabela('transactions')} "
            "WHERE customer_id = @customer_id AND date BETWEEN @inicio AND @fim"
            f"{filtro_categoria} ORDER BY date",
            **parametros,
        )
        return [project_transaction(linha) for linha in linhas]

    def get_card(self, customer_id: str) -> dict | None:
        linha = self._um(
            f"SELECT * FROM {self._tabela('credit_cards')} "
            "WHERE customer_id = @customer_id LIMIT 1",
            customer_id=customer_id,
        )
        return project_card(linha) if linha else None

    def get_goals(self, customer_id: str) -> list[dict]:
        linhas = self._linhas(
            f"SELECT * FROM {self._tabela('goals')} WHERE customer_id = @customer_id",
            customer_id=customer_id,
        )
        return [project_goal(linha) for linha in linhas]
