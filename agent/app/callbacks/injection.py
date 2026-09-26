"""Detecção heurística de prompt injection.

Vale para o texto do usuário e para o texto que vem dos dados: a descrição de um
Pix é escrita por terceiro e nunca é confiável.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Verbo de override + alvo a até 20 caracteres de distância. Âncoras rígidas
# ("desconsidere" colado em "instrucoes") deixavam passar as paráfrases mais
# naturais. "sem regras" foi removido: casava em pergunta legítima sobre
# contrato, recusava a conversa E somava strike.
PATTERNS = [
    r"(ignore|ignora|esqueca|desconsidere|despreze|disregard|forget)\b.{0,20}"
    r"(instruc|instruction|prompt|regra|rule|acima|above|anterior|previous)",
    r"(reveal|show|print|revele|mostre|diga)\b.{0,20}(system\s*)?(prompt|instruc)",
    r"(voce\s+agora|agora\s+voce)\s+(e|sera)\s+um",
    r"you\s+are\s+now\s+a",
    r"act\s+as\s+(if|though)\s+you",
    r"<\|.*?\|>",
]
_COMPILADOS = [re.compile(p) for p in PATTERNS]


@dataclass(frozen=True)
class Verdict:
    blocked: bool
    pattern: str | None = None


def _normalize(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in sem_acento if not unicodedata.combining(c)).lower()


def detect_injection(text: str) -> Verdict:
    alvo = _normalize(text)
    for rx in _COMPILADOS:
        if rx.search(alvo):
            return Verdict(blocked=True, pattern=rx.pattern)
    return Verdict(blocked=False)
