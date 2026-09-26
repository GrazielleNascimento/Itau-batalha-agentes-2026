def test_app_package_importa():
    import app  # noqa: F401


def test_root_agent_chama_se_orchestrator():
    from app.agent import root_agent

    assert root_agent.name == "orchestrator"


def test_manifesto_concorda_com_o_codigo():
    from pathlib import Path

    manifesto = Path(__file__).parents[2] / "agents-cli-manifest.yaml"
    texto = manifesto.read_text(encoding="utf-8")
    assert "root_agent_name: 'orchestrator'" in texto
