"""Único ponto de leitura de variáveis de ambiente do projeto."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_AGENT_ROOT = Path(__file__).resolve().parent.parent


def _flag(nome: str, padrao: bool) -> bool:
    return os.getenv(nome, str(padrao)).strip().lower() in ("1", "true", "yes")


@dataclass(frozen=True)
class Config:
    model_name: str
    prompt_version: str
    data_source: str
    data_dir: Path
    demo_mode: bool
    demo_customer_id: str
    memory_ttl_days: int
    guard_strikes_to_human: int
    use_model_armor: bool
    use_rag_engine: bool
    region: str


def load_config() -> Config:
    """Lê o ambiente a cada chamada, para que os testes possam variá-lo."""
    return Config(
        model_name=os.getenv("MODEL_NAME", "gemini-3.8-flash"),
        prompt_version=os.getenv("PROMPT_VERSION", "v1"),
        data_source=os.getenv("DATA_SOURCE", "local"),
        data_dir=(_AGENT_ROOT / os.getenv("DATA_DIR", "../data")).resolve(),
        demo_mode=_flag("DEMO_MODE", True),
        demo_customer_id=os.getenv("DEMO_CUSTOMER_ID", "FICT-0001"),
        memory_ttl_days=int(os.getenv("MEMORY_TTL_DAYS", "90")),
        guard_strikes_to_human=int(os.getenv("GUARD_STRIKES_TO_HUMAN", "3")),
        use_model_armor=_flag("USE_MODEL_ARMOR", False),
        use_rag_engine=_flag("USE_RAG_ENGINE", False),
        # REGION é onde o Cloud Run roda. GOOGLE_CLOUD_LOCATION, lido direto
        # pelo SDK do Gemini, é onde o modelo roda. Nunca derive uma da outra.
        region=os.getenv("REGION", "southamerica-east1"),
    )


def assert_flags_coerentes() -> None:
    """Recusa a subir com uma flag ligada que não tem implementação atrás.

    Uma flag que não faz nada em silêncio é pior que uma flag ausente: alguém
    liga, acredita ter a proteção, e só descobre quando ela era necessária.
    Mesmo princípio da fábrica de DataSource, que recusa um modo desconhecido.
    """
    cfg = load_config()

    if cfg.use_rag_engine:
        raise ValueError(
            "USE_RAG_ENGINE=true, mas o Vertex AI RAG Engine não está implementado. "
            "A busca de conhecimento hoje é local, em data/knowledge/. "
            "Use USE_RAG_ENGINE=false."
        )

    if cfg.use_model_armor:
        from app.callbacks.model_armor import assert_configurado

        assert_configurado()
