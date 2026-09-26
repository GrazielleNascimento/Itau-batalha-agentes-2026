"""Perfis contrastantes de cliente. O extrato é derivado daqui, não sorteado."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Archetype:
    key: str
    label_pt: str
    income_range: tuple[int, int]
    age_range: tuple[int, int]
    suitability: str
    # fração da renda gasta por mês, somando todas as categorias
    spend_ratio: float
    revolving_range: tuple[int, int]
    savings_range: tuple[int, int]


ARCHETYPES: list[Archetype] = [
    Archetype(
        "indebted",
        "endividado",
        (2500, 5000),
        (28, 50),
        "conservador",
        1.10,
        (3000, 9000),
        (0, 300),
    ),
    Archetype(
        "organized",
        "organizado",
        (7000, 15000),
        (33, 55),
        "moderado",
        0.62,
        (0, 0),
        (20000, 60000),
    ),
    Archetype(
        "early_career",
        "início de carreira",
        (1800, 3200),
        (19, 26),
        "arrojado",
        0.95,
        (400, 1500),
        (0, 1200),
    ),
    Archetype(
        "near_retirement",
        "perto da aposentadoria",
        (9000, 20000),
        (56, 66),
        "conservador",
        0.70,
        (0, 600),
        (80000, 250000),
    ),
    Archetype(
        "variable_income",
        "renda variável",
        (3000, 18000),
        (27, 48),
        "arrojado",
        0.85,
        (0, 4000),
        (1000, 25000),
    ),
]
