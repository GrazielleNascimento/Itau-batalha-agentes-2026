import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / "infra" / "scripts"))
import switch_project  # noqa: E402


@pytest.fixture
def env(tmp_path, monkeypatch):
    destino = tmp_path / "agent"
    destino.mkdir()
    arquivo = destino / ".env"
    arquivo.write_text(
        "GOOGLE_GENAI_USE_VERTEXAI=false\n"
        "GEMINI_API_KEY=chave-do-plano-b\n"
        "GOOGLE_CLOUD_LOCATION=global\n"
        "DATA_SOURCE=local\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    return arquivo


def test_modo_vertex_vira_o_toggle(env):
    switch_project.main("meu-projeto", "southamerica-east1", "vertex")
    texto = env.read_text(encoding="utf-8")
    assert "GOOGLE_GENAI_USE_VERTEXAI=true" in texto
    assert "GOOGLE_CLOUD_PROJECT=meu-projeto" in texto
    assert "REGION=southamerica-east1" in texto


def test_modo_local_volta_o_toggle(env):
    switch_project.main("meu-projeto", "southamerica-east1", "vertex")
    switch_project.main("meu-projeto", "southamerica-east1", "local")
    assert "GOOGLE_GENAI_USE_VERTEXAI=false" in env.read_text(encoding="utf-8")


def test_nunca_perde_a_chave_do_plano_b(env):
    switch_project.main("meu-projeto", "southamerica-east1", "vertex")
    assert "GEMINI_API_KEY=chave-do-plano-b" in env.read_text(encoding="utf-8")


def test_nao_duplica_variaveis_em_chamadas_repetidas(env):
    for _ in range(3):
        switch_project.main("p", "r", "vertex")
    linhas = env.read_text(encoding="utf-8").splitlines()
    chaves = [x.split("=", 1)[0] for x in linhas if "=" in x and not x.startswith("#")]
    assert len(chaves) == len(set(chaves)), chaves


def test_modo_invalido_e_recusado(env):
    with pytest.raises(SystemExit):
        switch_project.main("p", "r", "quantico")
