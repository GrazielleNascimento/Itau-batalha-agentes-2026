"""Memória local em SQLite. Sem ORM."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.config import load_config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS preferences (
    customer_id      TEXT NOT NULL,
    key              TEXT NOT NULL,
    value            TEXT NOT NULL,
    created_at       TEXT NOT NULL,
    expires_at       TEXT NOT NULL,
    consent_given_at TEXT NOT NULL,
    PRIMARY KEY (customer_id, key)
);
"""


class SqliteMemoryStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    async def save_preference(
        self,
        customer_id: str,
        key: str,
        value: str,
        consent_given_at: str | None,
        ttl_days: int,
    ) -> bool:
        """Grava só com consentimento. Sem ele, recusa e não escreve nada."""
        if not consent_given_at:
            return False
        agora = datetime.now(UTC)
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO preferences VALUES (?,?,?,?,?,?)",
                (
                    customer_id,
                    key,
                    value,
                    agora.isoformat(),
                    (agora + timedelta(days=ttl_days)).isoformat(),
                    consent_given_at,
                ),
            )
        return True

    async def get_profile_summary(self, customer_id: str) -> dict:
        """Devolve as preferências vivas. As expiradas são filtradas e apagadas."""
        agora = datetime.now(UTC).isoformat()
        with self._conn() as c:
            c.execute(
                "DELETE FROM preferences WHERE customer_id = ? AND expires_at <= ?",
                (customer_id, agora),
            )
            linhas = c.execute(
                "SELECT key, value, expires_at FROM preferences WHERE customer_id = ?",
                (customer_id,),
            ).fetchall()
        return {
            "preferences": {k: v for k, v, _ in linhas},
            "expires_at": {k: e for k, _, e in linhas},
        }

    async def delete_all(self, customer_id: str) -> int:
        """Direito de exclusão (LGPD). Devolve quantas linhas foram apagadas."""
        with self._conn() as c:
            cur = c.execute(
                "DELETE FROM preferences WHERE customer_id = ?", (customer_id,)
            )
            return cur.rowcount


def get_local_memory_store() -> SqliteMemoryStore:
    """Construtor do backend local. A escolha do backend é da factory."""
    return SqliteMemoryStore(load_config().data_dir / "memory.db")
