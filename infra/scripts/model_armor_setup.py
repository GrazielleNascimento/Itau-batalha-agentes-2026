#!/usr/bin/env python3
"""Cria ou atualiza o template do Model Armor. Idempotente.

O template é configuração de segurança: precisa ser código, para existir
igual no projeto do evento. Um template criado à mão ficou sem os quatro
filtros de IA responsável — foi assim que apareceu "Nenhum" no console.

    python3 infra/scripts/model_armor_setup.py --project X [--location us-central1] [--template batalha-agentes-guard]

Assinaturas verificadas por introspecção da biblioteca instalada (regra 6).
Model Armor NÃO existe em southamerica-east1; o texto que chega aqui já vem
mascarado pelo before_model.
"""

from __future__ import annotations

import argparse
import sys

from google.cloud import modelarmor_v1 as ma

RAI_TYPES = (
    ma.RaiFilterType.HATE_SPEECH,
    ma.RaiFilterType.DANGEROUS,
    ma.RaiFilterType.SEXUALLY_EXPLICIT,
    ma.RaiFilterType.HARASSMENT,
)


def template_name(project: str, location: str, template: str) -> str:
    return f"projects/{project}/locations/{location}/templates/{template}"


def build_filter_config() -> ma.FilterConfig:
    """Injeção em LOW (queremos pegar paráfrase); IA responsável em MEDIUM
    ('perigoso' em LOW barra linguagem financeira legítima)."""
    return ma.FilterConfig(
        rai_settings=ma.RaiFilterSettings(
            rai_filters=[
                ma.RaiFilterSettings.RaiFilter(
                    filter_type=t,
                    confidence_level=ma.DetectionConfidenceLevel.MEDIUM_AND_ABOVE,
                )
                for t in RAI_TYPES
            ]
        ),
        pi_and_jailbreak_filter_settings=ma.PiAndJailbreakFilterSettings(
            filter_enforcement=ma.PiAndJailbreakFilterSettings.PiAndJailbreakFilterEnforcement.ENABLED,
            confidence_level=ma.DetectionConfidenceLevel.LOW_AND_ABOVE,
        ),
        sdp_settings=ma.SdpFilterSettings(
            basic_config=ma.SdpBasicConfig(
                filter_enforcement=ma.SdpBasicConfig.SdpBasicConfigEnforcement.ENABLED
            )
        ),
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", required=True)
    ap.add_argument("--location", default="us-central1")
    ap.add_argument("--template", default="batalha-agentes-guard")
    args = ap.parse_args()

    from google.api_core.client_options import ClientOptions
    from google.api_core.exceptions import NotFound

    cli = ma.ModelArmorClient(
        client_options=ClientOptions(
            api_endpoint=f"modelarmor.{args.location}.rep.googleapis.com"
        )
    )
    nome = template_name(args.project, args.location, args.template)
    tpl = ma.Template(name=nome, filter_config=build_filter_config())
    try:
        cli.get_template(name=nome)
        cli.update_template(
            request=ma.UpdateTemplateRequest(
                template=tpl, update_mask={"paths": ["filter_config"]}
            )
        )
        print(f"atualizado: {nome}", file=sys.stderr)
    except NotFound:
        cli.create_template(
            request=ma.CreateTemplateRequest(
                parent=f"projects/{args.project}/locations/{args.location}",
                template_id=args.template,
                template=ma.Template(filter_config=build_filter_config()),
            )
        )
        print(f"criado: {nome}", file=sys.stderr)
    print(nome)
    return 0


if __name__ == "__main__":
    sys.exit(main())
