import pytest

from app.config import load_config


def test_defaults(monkeypatch):
    for chave in ("MODEL_NAME", "DATA_SOURCE", "DEMO_MODE", "DEMO_CUSTOMER_ID", "REGION"):
        monkeypatch.delenv(chave, raising=False)
    cfg = load_config()
    assert cfg.model_name == "gemini-3.8-flash"
    assert cfg.data_source == "local"
    assert cfg.demo_mode is True
    assert cfg.demo_customer_id == "FICT-0001"
    assert cfg.region == "southamerica-east1"


def test_env_sobrescreve(monkeypatch):
    monkeypatch.setenv("MODEL_NAME", "outro-modelo")
    monkeypatch.setenv("DEMO_MODE", "false")
    cfg = load_config()
    assert cfg.model_name == "outro-modelo"
    assert cfg.demo_mode is False


def test_region_e_location_sao_independentes(monkeypatch):
    monkeypatch.setenv("REGION", "southamerica-east1")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "global")
    cfg = load_config()
    assert cfg.region == "southamerica-east1"
    import os

    assert os.environ["GOOGLE_CLOUD_LOCATION"] == "global"


def test_data_dir_e_absoluto(monkeypatch):
    monkeypatch.delenv("DATA_DIR", raising=False)
    cfg = load_config()
    assert cfg.data_dir.is_absolute()
    assert cfg.data_dir.name == "data"


def test_env_example_sai_em_modo_local():
    """I11: vinha com GOOGLE_GENAI_USE_VERTEXAI=true e um projeto placeholder.
    `make setup && make run` numa máquina limpa dava erro de autenticação contra
    um projeto inexistente, não 'defina GEMINI_API_KEY'."""
    from pathlib import Path

    texto = (Path(__file__).parents[2] / ".env.example").read_text(encoding="utf-8")
    ativas = [x.strip() for x in texto.splitlines() if x.strip() and not x.startswith("#")]
    assert "GOOGLE_GENAI_USE_VERTEXAI=false" in ativas
    assert any(x.startswith("GEMINI_API_KEY=") for x in ativas)
    assert not any("your-gcp-project-id" in x for x in ativas)


def test_use_rag_engine_ligado_falha_alto(monkeypatch):
    """Flag que não faz nada em silêncio dá falsa sensação de proteção.
    RAG Engine não está implementado: ligar a flag tem de doer."""
    from app.config import assert_flags_coerentes

    monkeypatch.setenv("USE_RAG_ENGINE", "true")
    with pytest.raises(ValueError, match="USE_RAG_ENGINE"):
        assert_flags_coerentes()


def test_use_model_armor_ligado_sem_projeto_falha_alto(monkeypatch):
    from app.config import assert_flags_coerentes

    monkeypatch.setenv("USE_RAG_ENGINE", "false")
    monkeypatch.setenv("USE_MODEL_ARMOR", "true")
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    with pytest.raises(ValueError, match="GOOGLE_CLOUD_PROJECT"):
        assert_flags_coerentes()


def test_flags_desligadas_nao_reclamam(monkeypatch):
    from app.config import assert_flags_coerentes

    monkeypatch.setenv("USE_RAG_ENGINE", "false")
    monkeypatch.setenv("USE_MODEL_ARMOR", "false")
    assert_flags_coerentes()
