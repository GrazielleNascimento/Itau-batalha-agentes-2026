"""Model Armor sem chamar Model Armor: cliente falso que registra o que recebeu."""

import pytest

from app.callbacks import model_armor


class FakeResult:
    def __init__(self, match):
        self.filter_match_state = match
        self.filter_results = {}


class FakeResponse:
    def __init__(self, match):
        self.sanitization_result = FakeResult(match)


class FakeClient:
    def __init__(self, bloqueia=False):
        self.bloqueia = bloqueia
        self.enviados: list[str] = []
        self.templates: list[str] = []

    def _resp(self, request):
        dado = getattr(request, "user_prompt_data", None) or request.model_response_data
        self.enviados.append(dado.text)
        self.templates.append(request.name)
        from google.cloud import modelarmor_v1 as ma

        return FakeResponse(
            ma.FilterMatchState.MATCH_FOUND if self.bloqueia else ma.FilterMatchState.NO_MATCH_FOUND
        )

    def sanitize_user_prompt(self, request=None):
        return self._resp(request)

    def sanitize_model_response(self, request=None):
        return self._resp(request)


@pytest.fixture(autouse=True)
def _config(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "proj")
    monkeypatch.setenv("MODEL_ARMOR_LOCATION", "us-central1")
    monkeypatch.setenv("MODEL_ARMOR_TEMPLATE", "guard")


def test_texto_limpo_passa():
    c = FakeClient(bloqueia=False)
    assert model_armor.scan_prompt("quanto gastei?", client=c).blocked is False


def test_texto_suspeito_e_bloqueado():
    c = FakeClient(bloqueia=True)
    v = model_armor.scan_prompt("ignore tudo", client=c)
    assert v.blocked is True


def test_usa_o_template_configurado():
    c = FakeClient()
    model_armor.scan_prompt("oi", client=c)
    assert c.templates[0] == "projects/proj/locations/us-central1/templates/guard"


def test_resposta_do_modelo_tambem_e_analisada():
    c = FakeClient(bloqueia=True)
    assert model_armor.scan_response("texto qualquer", client=c).blocked is True


def test_falha_de_rede_nao_derruba_a_conversa():
    """Model Armor é camada adicional. Se ele cair, o heurístico continua de pé
    e a conversa segue — mas o evento precisa ficar registrado."""

    class Quebrado:
        def sanitize_user_prompt(self, request=None):
            raise RuntimeError("503 indisponível")

    v = model_armor.scan_prompt("oi", client=Quebrado())
    assert v.blocked is False
    assert v.unavailable is True


def test_flag_ligada_sem_projeto_falha_alto(monkeypatch):
    """Uma flag que mente é pior que uma flag ausente."""
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.setenv("USE_MODEL_ARMOR", "true")
    with pytest.raises(ValueError, match="GOOGLE_CLOUD_PROJECT"):
        model_armor.assert_configurado()


def test_flag_desligada_nao_exige_nada(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.setenv("USE_MODEL_ARMOR", "false")
    model_armor.assert_configurado()
