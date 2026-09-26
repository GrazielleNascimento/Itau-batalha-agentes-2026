import csv

from data.generator.generate import MALICIOUS_DESCRIPTION, generate_all


def _linhas(caminho):
    with open(caminho, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_determinismo(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    generate_all(a, seed=42)
    generate_all(b, seed=42)
    for nome in ("customers", "accounts", "transactions", "credit_cards", "goals"):
        assert (a / f"{nome}.csv").read_bytes() == (b / f"{nome}.csv").read_bytes()


def test_ids_sao_ficticios(tmp_path):
    generate_all(tmp_path, seed=42)
    for linha in _linhas(tmp_path / "customers.csv"):
        assert linha["customer_id"].startswith("FICT-")


def test_cinquenta_clientes_e_cinco_arquetipos(tmp_path):
    generate_all(tmp_path, seed=42)
    clientes = _linhas(tmp_path / "customers.csv")
    assert len(clientes) == 50
    assert len({c["archetype"] for c in clientes}) == 5


def test_arquetipos_produzem_extratos_contrastantes(tmp_path):
    generate_all(tmp_path, seed=42)
    cartoes = {c["customer_id"]: c for c in _linhas(tmp_path / "credit_cards.csv")}
    clientes = {c["customer_id"]: c for c in _linhas(tmp_path / "customers.csv")}
    rotativo_endividado = [
        float(cartoes[cid]["revolving_balance"])
        for cid, c in clientes.items()
        if c["archetype"] == "indebted"
    ]
    rotativo_organizado = [
        float(cartoes[cid]["revolving_balance"])
        for cid, c in clientes.items()
        if c["archetype"] == "organized"
    ]
    assert min(rotativo_endividado) > max(rotativo_organizado)


def test_cada_cliente_tem_um_pix_malicioso(tmp_path):
    generate_all(tmp_path, seed=42)
    transacoes = _linhas(tmp_path / "transactions.csv")
    por_cliente = {}
    for t in transacoes:
        if t["description"] == MALICIOUS_DESCRIPTION:
            por_cliente[t["customer_id"]] = por_cliente.get(t["customer_id"], 0) + 1
    assert len(por_cliente) == 50
    assert set(por_cliente.values()) == {1}


def test_csv_de_origem_tem_cpf_e_nome_completo(tmp_path):
    """I10: sem PII na origem, o teste anti-CPF das tools passa por vacuidade.
    A minimização precisa ter algo de que minimizar."""
    from app.callbacks.pii import cpf_valido, so_digitos

    generate_all(tmp_path, seed=42)
    clientes = _linhas(tmp_path / "customers.csv")
    assert all(c["cpf"] for c in clientes)
    assert all(c["full_name"] for c in clientes)
    # CPFs sintéticos, mas com checksum válido: o mascaramento tem de reconhecê-los.
    assert all(cpf_valido(so_digitos(c["cpf"])) for c in clientes)
    assert len({c["cpf"] for c in clientes}) == 50
