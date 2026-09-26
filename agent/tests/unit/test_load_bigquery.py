import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).parents[3]
SCRIPT = RAIZ / "infra" / "scripts" / "load_bigquery.sh"
TABELAS = {"customers", "accounts", "transactions", "credit_cards", "goals"}


@pytest.fixture(scope="module")
def dry():
    return subprocess.run(
        ["bash", str(SCRIPT), "--dry-run"],
        capture_output=True, text=True, cwd=RAIZ,
        env={"PATH": "/usr/bin:/bin", "PROJECT_ID": "proj-teste"},
    )


def test_dry_run_nao_falha(dry):
    assert dry.returncode == 0, dry.stderr


def test_cria_o_dataset_do_handoff(dry):
    assert "mk" in dry.stdout
    assert "batalha_agentes" in dry.stdout


def test_carrega_as_cinco_tabelas(dry):
    for t in TABELAS:
        assert t in dry.stdout, t
    # conta a operação, não a grafia do comando (as flags vêm antes do verbo)
    assert dry.stdout.count("--source_format=CSV") == 5


def test_dataset_fica_na_regiao_configurada(dry):
    assert "southamerica-east1" in dry.stdout


def test_carga_e_idempotente(dry):
    """Rodar duas vezes não pode duplicar linhas."""
    assert "--replace" in dry.stdout


def test_sem_project_id_recusa():
    r = subprocess.run(
        ["bash", str(SCRIPT), "--dry-run"],
        capture_output=True, text=True, cwd=RAIZ, env={"PATH": "/usr/bin:/bin"},
    )
    assert r.returncode != 0
    assert "PROJECT_ID" in (r.stdout + r.stderr)


def test_schema_e_declarado_e_nao_adivinhado(dry):
    """--autodetect não serve aqui: em tabelas cujas colunas são todas texto
    (customers), ele não distingue cabeçalho de dado e gera string_field_N.
    Schema explícito é contrato; palpite é bug silencioso."""
    assert "--autodetect" not in dry.stdout
    assert "--schema" in dry.stdout
    assert "--skip_leading_rows=1" in dry.stdout
    assert "customer_id:STRING" in dry.stdout


def test_colunas_numericas_nao_viram_texto(dry):
    """Se amount for STRING, toda soma quebra ou mente."""
    assert "amount:FLOAT" in dry.stdout
    assert "balance:FLOAT" in dry.stdout


def test_apaga_a_tabela_antes_de_carregar(dry):
    """--replace numa tabela existente MANTÉM o schema antigo: o autodetect não
    roda e o cabeçalho entra como linha de dado. A tabela precisa nascer nova."""
    assert dry.stdout.count("bq rm") == 5 or dry.stdout.count(" rm ") == 5
