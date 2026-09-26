from app.tools.knowledge import search_knowledge


def test_encontra_por_termo_exato():
    r = search_knowledge("juros compostos")
    assert r["results"], r
    assert "juros" in r["results"][0]["title"].lower()


def test_insensivel_a_acento_e_caixa():
    com = search_knowledge("orçamento")
    sem = search_knowledge("ORCAMENTO")
    assert com["results"] and sem["results"]
    assert com["results"][0]["title"] == sem["results"][0]["title"]


def test_query_vazia_nao_devolve_tudo():
    r = search_knowledge("")
    assert r["results"] == []
    assert r["reason"]


def test_query_so_com_stopwords_nao_devolve_tudo():
    r = search_knowledge("de a o que")
    assert r["results"] == []
    assert r["reason"]


def test_termo_inexistente_devolve_vazio():
    r = search_knowledge("zebra astronauta quantica")
    assert r["results"] == []


def test_titulo_pesa_mais_que_mencao_de_passagem():
    """I8: com um termo só, todo doc que cita a palavra empatava em 1.0 e o
    desempate era alfabético — 'orçamento' devolvia 'Dívida boa e dívida ruim'."""
    assert search_knowledge("orcamento")["results"][0]["title"] == "Orçamento mensal"
    assert (
        search_knowledge("reserva de emergencia")["results"][0]["title"]
        == "Reserva de emergência"
    )
    assert search_knowledge("rotativo")["results"][0]["title"] == "Rotativo do cartão de crédito"
