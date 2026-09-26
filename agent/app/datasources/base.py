"""Contrato de acesso a dados. Trocar local por BigQuery não muda as tools."""

from __future__ import annotations

from typing import Protocol


class DataSource(Protocol):
    def get_customer(self, customer_id: str) -> dict | None: ...
    def get_accounts(self, customer_id: str) -> dict | None: ...
    def get_transactions(
        self,
        customer_id: str,
        start_date: str,
        end_date: str,
        category: str | None = None,
    ) -> list[dict]: ...
    def get_card(self, customer_id: str) -> dict | None: ...
    def get_goals(self, customer_id: str) -> list[dict]: ...
