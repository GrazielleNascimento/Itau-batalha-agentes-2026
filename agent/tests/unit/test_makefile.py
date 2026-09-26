from pathlib import Path

ALVOS = {"setup", "data", "run", "test", "test-llm", "lint", "switch-project"}


def _makefile() -> str:
    return (Path(__file__).parents[3] / "Makefile").read_text(encoding="utf-8")


def test_makefile_tem_todos_os_alvos():
    texto = _makefile()
    declarados = {
        linha.split(":")[0]
        for linha in texto.splitlines()
        if ":" in linha and not linha.startswith(("\t", "#", ".", " "))
    }
    assert ALVOS <= declarados, ALVOS - declarados


def test_switch_project_exige_project_id():
    texto = _makefile()
    assert "PROJECT_ID" in texto
    assert "gcloud config set project" in texto


def test_alvos_sao_phony():
    # Sem .PHONY o alvo `data` colide com o diretório data/ e o make não faz nada.
    texto = _makefile()
    linha = next(x for x in texto.splitlines() if x.startswith(".PHONY"))
    for alvo in ALVOS:
        assert alvo in linha, alvo
