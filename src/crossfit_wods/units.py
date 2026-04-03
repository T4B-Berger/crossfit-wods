from __future__ import annotations

LB_TO_KG = 0.45359237
POOD_TO_KG = 16.3807
MILE_TO_M = 1609.344
YARD_TO_M = 0.9144
FOOT_TO_M = 0.3048
INCH_TO_M = 0.0254


def to_kg(value: float, unit: str) -> float:
    u = unit.lower().strip()
    if u in {"kg", "kgs"}:
        return value
    if u in {"lb", "lbs", "pound", "pounds"}:
        return value * LB_TO_KG
    if u in {"pood", "poods"}:
        return value * POOD_TO_KG
    raise ValueError(f"Unsupported load unit: {unit}")


def to_meters(value: float, unit: str) -> float:
    u = unit.lower().strip()
    if u in {"m", "meter", "meters", "metre", "metres"}:
        return value
    if u in {"km", "kilometer", "kilometers", "kilometre", "kilometres"}:
        return value * 1000
    if u in {"mile", "miles", "mi"}:
        return value * MILE_TO_M
    if u in {"yard", "yards", "yd"}:
        return value * YARD_TO_M
    if u in {"foot", "feet", "ft"}:
        return value * FOOT_TO_M
    if u in {"inch", "inches", "in"}:
        return value * INCH_TO_M
    raise ValueError(f"Unsupported distance unit: {unit}")
