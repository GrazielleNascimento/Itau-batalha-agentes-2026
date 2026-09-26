import json
from pathlib import Path

DATASET = Path(__file__).parents[2] / "agent" / "tests" / "eval" / "datasets" / "basic-dataset.json"
if not DATASET.exists():
    DATASET = Path(__file__).parents[1] / "eval" / "datasets" / "basic-dataset.json"

# Os cinco eixos que a Fase 6 do HANDOFF exige.
EIXOS = {"roteamento", "numero_via_tool", "fora_de_escopo", "injection", "confirmacao"}


def _casos():
    return json.loads(DATASET.read_text(encoding="utf-8"))["eval_cases"]


def test_dataset_e_json_valido_com_dez_casos():
    casos = _casos()
    assert len(casos) >= 10, f"apenas {len(casos)} casos"


def test_ids_sao_unicos():
    ids = [c["eval_case_id"] for c in _casos()]
    assert len(ids) == len(set(ids)), ids


def test_todos_os_eixos_do_handoff_estao_cobertos():
    eixos = {c["eval_case_id"].split("__")[0] for c in _casos()}
    assert EIXOS <= eixos, EIXOS - eixos


def test_todo_caso_tem_prompt_de_usuario():
    for c in _casos():
        assert c["prompt"]["role"] == "user", c["eval_case_id"]
        assert c["prompt"]["parts"][0]["text"].strip(), c["eval_case_id"]


def test_dataset_nao_tem_conteudo_de_jornada_especifica():
    """O template é genérico: nada aqui pode presumir a jornada do evento."""
    bruto = DATASET.read_text(encoding="utf-8").lower()
    for proibido in ("itau", "itaú", "weather", "san francisco", "capital of france"):
        assert proibido not in bruto, proibido


def test_nenhum_cpf_real_no_dataset():
    import re

    from app.callbacks.pii import cpf_valido, so_digitos

    bruto = DATASET.read_text(encoding="utf-8")
    for m in re.finditer(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}", bruto):
        # O único CPF permitido é o sintético usado no caso de mascaramento.
        assert cpf_valido(so_digitos(m.group())), "CPF inválido não serve para testar máscara"
