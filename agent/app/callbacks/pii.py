"""ok,. Sem dependência de ADK, para ser testável sozinho."""

from __future__ import annotations

import re

# Regex deliberadamente frouxo quanto ao separador: o dígito verificador em
# cpf_valido() é o filtro de falso positivo, não o formato. "529 982 247 25" e
# "529.982.247.25" são grafias comuns e escapavam de um padrão só com . e -.
CPF_RE = re.compile(r"(?<!\d)\d{3}[.\s-]?\d{3}[.\s-]?\d{3}[-.\s]?\d{2}(?!\d)")
CARD_RE = re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
# (?<!\d) e (?!\d): sem isso o padrão casa 10 dígitos DENTRO de uma sequência
# maior, e "protocolo 12345678901" virava telefone.
PHONE_RE = re.compile(r"(?<!\d)(?:\+55\s?)?\(?\d{2}\)?\s?9?\d{4}-?\d{4}(?!\d)")


def so_digitos(texto: str) -> str:
    return re.sub(r"\D", "", texto)


def cpf_valido(digitos: str) -> bool:
    """Valida os dois dígitos verificadores. Sem isso, todo número de 11 dígitos vira CPF."""
    if len(digitos) != 11 or len(set(digitos)) == 1:
        return False
    for n in (9, 10):
        soma = sum(int(digitos[i]) * ((n + 1) - i) for i in range(n))
        if (soma * 10) % 11 % 10 != int(digitos[n]):
            return False
    return True


def luhn_valido(digitos: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digitos)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def mask_pii(text: str) -> tuple[str, list[str]]:
    """Mascara CPF, cartão, e-mail e telefone. Devolve o texto e os tipos encontrados."""
    achados: list[str] = []

    def _cpf(m: re.Match) -> str:
        if cpf_valido(so_digitos(m.group())):
            achados.append("cpf")
            return "[CPF]"
        return m.group()

    def _card(m: re.Match) -> str:
        if luhn_valido(so_digitos(m.group())):
            achados.append("card")
            return "[CARTAO]"
        return m.group()

    # Cartão antes de CPF: senão o regex de CPF morde um pedaço do número do cartão.
    texto = CARD_RE.sub(_card, text)
    texto = CPF_RE.sub(_cpf, texto)
    if EMAIL_RE.search(texto):
        achados.append("email")
        texto = EMAIL_RE.sub("[EMAIL]", texto)
    if PHONE_RE.search(texto):
        achados.append("phone")
        texto = PHONE_RE.sub("[TELEFONE]", texto)
    return texto, sorted(set(achados))
