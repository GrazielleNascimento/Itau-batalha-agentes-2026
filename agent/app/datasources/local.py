"""Fonte de dados local, lendo os CSVs sintéticos."""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

from app.config import load_config
from app.datasources.projections import (
    project_card,
    project_customer,
    project_goal,
    project_transaction,
)


class MissingDataError(RuntimeError):
    """Os CSVs sintéticos não existem ainda."""


class LocalDataSource:
    @staticmethod
    @lru_cache(maxsize=8)
    def _carregar(nome: str, pasta: str) -> tuple[dict, ...]:
        caminho = Path(pasta) / f"{nome}.csv"
        if not caminho.exists():
            raise MissingDataError(
                f"{caminho} não existe. Rode `make data` para gerar os dados sintéticos."
            )
        with open(caminho, encoding="utf-8") as fh:
            return tuple(csv.DictReader(fh))

    def _linhas(self, nome: str) -> tuple[dict, ...]:
        return self._carregar(nome, str(load_config().data_dir / "synthetic"))

    def get_customer(self, customer_id: str) -> dict | None:
        for r in self._linhas("customers"):
            if r["customer_id"] == customer_id:
                return project_customer(r)
        return None

    def get_accounts(self, customer_id: str) -> dict | None:
        for r in self._linhas("accounts"):
            if r["customer_id"] == customer_id:
                return {
                    "balance": float(r["balance"]),
                    "overdraft_limit": float(r["overdraft_limit"]),
                }
        return None

    def get_transactions(
        self,
        customer_id: str,
        start_date: str,
        end_date: str,
        category: str | None = None,
    ) -> list[dict]:
        # Datas invertidas não podem virar resultado vazio silencioso.
        inicio, fim = sorted((start_date, end_date))
        return [
            project_transaction(r)
            for r in self._linhas("transactions")
            if r["customer_id"] == customer_id
            and inicio <= r["date"] <= fim
            and (category is None or r["category"] == category)
        ]

    def get_card(self, customer_id: str) -> dict | None:
        for r in self._linhas("credit_cards"):
            if r["customer_id"] == customer_id:
                return project_card(r)
        return None

    def get_goals(self, customer_id: str) -> list[dict]:
        return [
            project_goal(r)
            for r in self._linhas("goals")
            if r["customer_id"] == customer_id
        ]
