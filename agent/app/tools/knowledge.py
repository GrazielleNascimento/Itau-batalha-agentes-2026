"""Busca na base de conhecimento local de educação financeira."""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

from app.config import load_config

# Palavras curtas e vazias que, sozinhas, casariam com qualquer texto.
STOPWORDS = {
    "a",
    "as",
    "o",
    "os",
    "de",
    "da",
    "do",
    "das",
    "dos",
    "e",
    "em",
    "no",
    "na",
    "um",
    "uma",
    "que",
    "para",
    "por",
    "com",
    "se",
    "ao",
    "aos",
}


def _normalize(texto: str) -> str:
    """Minúsculas e sem acento: 'Orçamento' e 'orcamento' viram a mesma coisa."""
    sem_acento = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return sem_acento.lower()


def _tokens(texto: str) -> set[str]:
    return {
        t
        for t in re.findall(r"\w+", _normalize(texto))
        if t not in STOPWORDS and len(t) > 2
    }


@lru_cache(maxsize=4)
def _documentos(pasta: str) -> tuple[tuple[str, str, frozenset[str]], ...]:
    from pathlib import Path

    docs = []
    for caminho in sorted(Path(pasta).glob("*.md")):
        corpo = caminho.read_text(encoding="utf-8")
        titulo = corpo.splitlines()[0].lstrip("# ").strip()
        docs.append((titulo, corpo, frozenset(_tokens(corpo))))
    return tuple(docs)


def search_knowledge(query: str) -> dict:
    """Busca conceitos de educação financeira na base de conhecimento.

    Args:
        query: termo ou pergunta sobre um conceito financeiro.

    Returns:
        results: lista ordenada por relevância, com title, excerpt e score.
        reason: preenchido quando a busca não pôde ser feita.
    """
    termos = _tokens(query)
    if not termos:
        return {"results": [], "reason": "consulta vazia ou só com palavras genéricas"}

    pasta = str(load_config().data_dir / "knowledge")
    encontrados = []
    for titulo, corpo, tokens_doc in _documentos(pasta):
        comuns = termos & tokens_doc
        if not comuns:
            continue
        # Sem o peso do título, toda menção de passagem empata em 1.0 e o
        # desempate vira alfabético: "orçamento" devolvia "Dívida boa e ruim".
        no_titulo = termos & _tokens(titulo)
        encontrados.append(
            {
                "title": titulo,
                "excerpt": corpo[:400],
                "score": round(len(comuns) / len(termos) + 0.5 * len(no_titulo), 3),
            }
        )
    encontrados.sort(key=lambda d: (-d["score"], d["title"]))
    return {"results": encontrados[:3], "reason": None}
