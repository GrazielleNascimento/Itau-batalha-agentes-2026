from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from google.adk.sessions.state import State

from app.memory.local import SqliteMemoryStore
from app.tools import memory_tools


def store(tmp_path):
    return SqliteMemoryStore(tmp_path / "m.db")


def ctx(customer_id="FICT-0001", consent=None):
    """Usa o State REAL do ADK, não um dict.

    Um dict tem .pop() e .__delitem__; o State do ADK não tem nenhum dos dois.
    Testar contra dict deixou passar um AttributeError que só apareceu no
    Cloud Run, na primeira vez que forget_me rodou de verdade.
    """
    valores = {"customer_id": customer_id}
    if consent:
        valores["consent_given_at"] = consent
    return SimpleNamespace(state=State(value=valores, delta={}))


async def test_sem_consentimento_nao_grava(tmp_path):
    s = store(tmp_path)
    assert await s.save_preference("FICT-0001", "canal", "whatsapp", None, 90) is False
    assert (await s.get_profile_summary("FICT-0001"))["preferences"] == {}


async def test_com_consentimento_grava_e_le(tmp_path):
    s = store(tmp_path)
    agora = datetime.now(UTC).isoformat()
    assert await s.save_preference("FICT-0001", "canal", "whatsapp", agora, 90) is True
    assert (await s.get_profile_summary("FICT-0001"))["preferences"]["canal"] == "whatsapp"


async def test_ttl_expirado_nao_e_devolvido(tmp_path):
    s = store(tmp_path)
    agora = datetime.now(UTC).isoformat()
    await s.save_preference("FICT-0001", "canal", "whatsapp", agora, ttl_days=-1)
    assert (await s.get_profile_summary("FICT-0001"))["preferences"] == {}


async def test_delete_all_apaga_tudo_do_cliente(tmp_path):
    s = store(tmp_path)
    agora = datetime.now(UTC).isoformat()
    await s.save_preference("FICT-0001", "a", "1", agora, 90)
    await s.save_preference("FICT-0001", "b", "2", agora, 90)
    await s.save_preference("FICT-0002", "c", "3", agora, 90)
    assert await s.delete_all("FICT-0001") == 2
    assert (await s.get_profile_summary("FICT-0001"))["preferences"] == {}
    assert (await s.get_profile_summary("FICT-0002"))["preferences"] == {"c": "3"}


async def test_memoria_atravessa_sessoes(tmp_path):
    caminho = tmp_path / "m.db"
    agora = datetime.now(UTC).isoformat()
    await SqliteMemoryStore(caminho).save_preference("FICT-0001", "canal", "app", agora, 90)
    outra = SqliteMemoryStore(caminho)
    assert (await outra.get_profile_summary("FICT-0001"))["preferences"]["canal"] == "app"


async def test_tool_recusa_sem_consentimento(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    r = await memory_tools.remember_preference("canal", "app", tool_context=ctx())
    assert r["saved"] is False
    assert "consentimento" in r["reason"].lower()


async def test_give_consent_grava_no_estado_e_habilita(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    c = ctx()
    assert "consent_given_at" not in c.state
    memory_tools.give_consent(tool_context=c)
    assert c.state["consent_given_at"]
    assert (await memory_tools.remember_preference("canal", "app", tool_context=c))["saved"] is True


async def test_forget_me_apaga(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    c = ctx(consent=datetime.now(UTC).isoformat())
    await memory_tools.remember_preference("canal", "app", tool_context=c)
    assert (await memory_tools.forget_me(tool_context=c))["deleted"] == 1
    assert (await memory_tools.recall_profile(tool_context=c))["preferences"] == {}


def test_consentimento_nao_vem_pre_semeado():
    # D7: consentimento é concedido na conversa, nunca pré-preenchido.
    assert "consent_given_at" not in ctx().state


async def test_ttl_futuro_continua_valido(tmp_path):
    s = store(tmp_path)
    agora = datetime.now(UTC).isoformat()
    await s.save_preference("FICT-0001", "canal", "app", agora, ttl_days=1)
    expira = datetime.fromisoformat(
        (await s.get_profile_summary("FICT-0001"))["expires_at"]["canal"]
    )
    assert expira > datetime.now(UTC) + timedelta(hours=1)


async def test_forget_me_revoga_o_consentimento(tmp_path, monkeypatch):
    """I7: apagar as linhas e manter consent_given_at no estado faz o próximo
    remember_preference gravar de novo sem perguntar nada."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    c = ctx(consent=datetime.now(UTC).isoformat())
    await memory_tools.remember_preference("canal", "app", tool_context=c)
    await memory_tools.forget_me(tool_context=c)

    # O que importa é o consentimento estar revogado, não a chave sumir:
    # o State do ADK não permite remover chave, só atribuir.
    assert not c.state.get("consent_given_at")
    depois = await memory_tools.remember_preference("canal", "whatsapp", tool_context=c)
    assert depois["saved"] is False
    assert (await memory_tools.recall_profile(tool_context=c))["preferences"] == {}
