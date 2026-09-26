#!/usr/bin/env python3
"""Cria (ou encontra) o Agent Engine que guarda sessão e memória do agente.

O agente serve pelo Cloud Run; o Agent Engine entra só como backend de
sessão (VertexAiSessionService) e memória (VertexAiMemoryBankService), para
que nada viva dentro do processo do container.

    python3 infra/scripts/agent_engine_setup.py --project X [--location us-central1]

Imprime o ID na última linha, para o Makefile capturar.
"""

from __future__ import annotations

import argparse
import sys

NOME = "batalha-agentes-memoria"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", required=True)
    ap.add_argument("--location", default="southamerica-east1")
    args = ap.parse_args()

    import vertexai
    from vertexai import agent_engines

    vertexai.init(
        project=args.project,
        location=args.location,
        staging_bucket=f"gs://{args.project}-agent-engine",
    )
    existentes = list(agent_engines.list(filter=f'display_name="{NOME}"'))
    if existentes:
        eng = existentes[0]
        print(f"já existia: {eng.resource_name}", file=sys.stderr)
    else:
        eng = agent_engines.create(
            display_name=NOME,
            description="Sessão e memória gerenciadas. O agente serve pelo Cloud Run.",
        )
        print(f"criado: {eng.resource_name}", file=sys.stderr)
    print(eng.resource_name.split("/")[-1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
