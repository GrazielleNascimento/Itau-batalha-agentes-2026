import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).parents[3]
SCRIPT = RAIZ / "infra" / "scripts" / "traffic_split.sh"


def _rodar(*args, **env_extra):
    env = {
        "PATH": "/usr/bin:/bin",
        "PROJECT_ID": "proj-teste",
        "REGION": "southamerica-east1",
        **env_extra,
    }
    return subprocess.run(
        ["bash", str(SCRIPT), *args], capture_output=True, text=True, cwd=RAIZ, env=env
    )


@pytest.fixture(scope="module")
def split():
    return _rodar("--dry-run")


def test_dry_run_nao_falha(split):
    assert split.returncode == 0, split.stderr


def test_marca_a_revisao_atual_como_controle(split):
    assert "update-traffic" in split.stdout
    assert "--set-tags" in split.stdout or "--update-tags" in split.stdout
    assert "v1" in split.stdout


def test_candidata_sobe_sem_trafego_e_com_tag(split):
    assert "--tag v2" in split.stdout or "--tag=v2" in split.stdout
    assert "--no-traffic" in split.stdout


def test_candidata_difere_apenas_por_variavel_de_ambiente(split):
    """O experimento é uma variável, não um branch."""
    assert "PROMPT_VERSION" in split.stdout


def test_divide_noventa_dez(split):
    assert "v1=90" in split.stdout
    assert "v2=10" in split.stdout


def test_rollback_manda_tudo_para_o_controle():
    r = _rodar("--rollback", "--dry-run")
    assert r.returncode == 0, r.stderr
    assert "v1=100" in r.stdout
    assert "v2=10" not in r.stdout


def test_permite_experimentar_modelo_em_vez_de_prompt():
    r = _rodar("--dry-run", VARIANT_ENV="MODEL_NAME=gemini-3.8-flash-lite")
    assert "MODEL_NAME=gemini-3.8-flash-lite" in r.stdout


def test_sem_project_id_recusa():
    r = subprocess.run(
        ["bash", str(SCRIPT), "--dry-run"],
        capture_output=True, text=True, cwd=RAIZ, env={"PATH": "/usr/bin:/bin"},
    )
    assert r.returncode != 0
    assert "PROJECT_ID" in (r.stdout + r.stderr)
