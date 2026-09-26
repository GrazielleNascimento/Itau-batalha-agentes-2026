"""Reaponta o .env para outro projeto GCP e alterna entre Vertex e AI Studio.

Um arquivo à parte porque cada linha de uma receita do make roda num shell
próprio, e um heredoc não sobrevive a isso.

O modo faz parte da troca: apontar o projeto sem virar GOOGLE_GENAI_USE_VERTEXAI
deixa o agente falando com o AI Studio enquanto você acha que está no Vertex.
"""

from __future__ import annotations

import pathlib
import re
import sys

MODOS = {"vertex": "true", "local": "false"}


def main(projeto: str, regiao: str, modo: str = "vertex") -> None:
    if modo not in MODOS:
        sys.exit(f"modo inválido: {modo!r}. Use um de: {', '.join(MODOS)}.")

    env = pathlib.Path("agent/.env")
    linhas = env.read_text(encoding="utf-8").splitlines() if env.exists() else []
    valores = {
        "GOOGLE_CLOUD_PROJECT": projeto,
        "REGION": regiao,
        "GOOGLE_GENAI_USE_VERTEXAI": MODOS[modo],
    }
    vistos: set[str] = set()
    saida: list[str] = []
    for linha in linhas:
        m = re.match(r"(\w+)=", linha)
        # GEMINI_API_KEY nunca é tocada: é o plano B se a nuvem falhar.
        if m and m.group(1) in valores and m.group(1) not in vistos:
            saida.append(f"{m.group(1)}={valores[m.group(1)]}")
            vistos.add(m.group(1))
        elif m and m.group(1) in vistos:
            continue  # duplicata de uma variável já reescrita
        else:
            saida.append(linha)
    saida += [f"{k}={v}" for k, v in valores.items() if k not in vistos]
    env.write_text("\n".join(saida) + "\n", encoding="utf-8")
    print(f"agent/.env -> projeto {projeto}, região {regiao}, modo {modo}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
