"""Prompts versionados em arquivo.

A versão ativa vem de PROMPT_VERSION, o que permite A/B entre revisões sem tocar
em código.
"""

from __future__ import annotations

from pathlib import Path

from app.config import load_config

_AQUI = Path(__file__).resolve().parent


def load_prompt(nome: str) -> str:
    versao = load_config().prompt_version
    caminho = _AQUI / versao / f"{nome}.md"
    if not caminho.exists():
        raise FileNotFoundError(
            f"Prompt {nome!r} não existe na versão {versao!r} ({caminho})."
        )
    return caminho.read_text(encoding="utf-8")
