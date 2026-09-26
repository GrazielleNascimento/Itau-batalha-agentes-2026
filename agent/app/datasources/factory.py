"""Escolhe a implementação de DataSource pela variável DATA_SOURCE."""

from __future__ import annotations

from app.config import load_config
from app.datasources.base import DataSource
from app.datasources.local import LocalDataSource


def get_data_source() -> DataSource:
    modo = load_config().data_source
    if modo == "local":
        return LocalDataSource()
    if modo == "evento":
        from app.datasources.evento import from_snapshot

        return from_snapshot(load_config().data_dir)

    if modo == "bigquery":
        import os

        from app.datasources.bigquery import BigQueryDataSource, _client_padrao

        projeto = os.getenv("GOOGLE_CLOUD_PROJECT")
        if not projeto:
            raise ValueError(
                "DATA_SOURCE=bigquery exige GOOGLE_CLOUD_PROJECT. "
                "Rode: make switch-project PROJECT_ID=... MODE=vertex"
            )
        return BigQueryDataSource(client=_client_padrao(), project=projeto)
    raise ValueError(f"DATA_SOURCE desconhecido: {modo!r}")
