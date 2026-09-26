"""A suíte não pode depender de `make data` ter rodado.

Num clone limpo, data/synthetic/ não existe (está no .gitignore). Sem esta
fixture, 14 testes falham no primeiro `make setup && make test` do dia.
"""

from __future__ import annotations

import os
import pathlib
from pathlib import Path

import pytest
from dotenv import load_dotenv

from data.generator.generate import generate_all

# O .env só era carregado pelo fast_api_app. Sem isto, GEMINI_API_KEY nunca
# chega ao os.environ do pytest: os testes de integração pulavam silenciosamente
# e os do scaffold falhavam com "No API key". Precisa rodar no import do
# conftest, antes dos módulos de teste, porque o skipif é avaliado no import.
load_dotenv(pathlib.Path(__file__).resolve().parents[1] / ".env")

_REPO_DATA = Path(__file__).resolve().parents[2] / "data"


@pytest.fixture(scope="session", autouse=True)
def dados_sinteticos(tmp_path_factory):
    """Gera os CSVs num diretório temporário e aponta DATA_DIR para lá."""
    raiz = tmp_path_factory.mktemp("data")
    generate_all(raiz / "synthetic", seed=42)
    # knowledge/ é versionado no repo; só o synthetic/ é gerado.
    (raiz / "knowledge").symlink_to(_REPO_DATA / "knowledge")
    anterior = os.environ.get("DATA_DIR")
    os.environ["DATA_DIR"] = str(raiz)
    yield raiz
    if anterior is None:
        os.environ.pop("DATA_DIR", None)
    else:
        os.environ["DATA_DIR"] = anterior
