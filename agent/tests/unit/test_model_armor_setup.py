"""O template do Model Armor é código, não clique: precisa existir igual no
projeto do evento. Aqui testamos só o construtor de configuração, que é puro."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3] / "infra" / "scripts"))
import model_armor_setup as setup  # noqa: E402
from google.cloud import modelarmor_v1 as ma  # noqa: E402


def test_liga_os_quatro_filtros_de_ia_responsavel():
    """Sem rai_settings o console mostra 'Nenhum' nos quatro — foi o que
    aconteceu no template criado à mão. Discurso de ódio, perigoso,
    sexualmente explícito e assédio são o mínimo para agente de banco."""
    cfg = setup.build_filter_config()
    tipos = {f.filter_type for f in cfg.rai_settings.rai_filters}
    assert tipos == {
        ma.RaiFilterType.HATE_SPEECH,
        ma.RaiFilterType.DANGEROUS,
        ma.RaiFilterType.SEXUALLY_EXPLICIT,
        ma.RaiFilterType.HARASSMENT,
    }


def test_rai_em_medium_para_nao_barrar_linguagem_financeira():
    """'Perigoso' em LOW pode barrar 'dívida perigosa', 'risco alto'. Guard
    bloqueando pergunta legítima custa mais que deixar passar caso raro."""
    cfg = setup.build_filter_config()
    assert {f.confidence_level for f in cfg.rai_settings.rai_filters} == {
        ma.DetectionConfidenceLevel.MEDIUM_AND_ABOVE
    }


def test_injection_continua_em_low():
    cfg = setup.build_filter_config()
    pi = cfg.pi_and_jailbreak_filter_settings
    assert pi.filter_enforcement == ma.PiAndJailbreakFilterSettings.PiAndJailbreakFilterEnforcement.ENABLED
    assert pi.confidence_level == ma.DetectionConfidenceLevel.LOW_AND_ABOVE


def test_sdp_basico_ligado():
    cfg = setup.build_filter_config()
    assert cfg.sdp_settings.basic_config.filter_enforcement == ma.SdpBasicConfig.SdpBasicConfigEnforcement.ENABLED


def test_nome_do_template_segue_o_projeto_e_a_regiao():
    assert setup.template_name("p", "us-central1", "t") == "projects/p/locations/us-central1/templates/t"
