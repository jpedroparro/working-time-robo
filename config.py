"""Configuração salva em config.json (tempos do pomodoro e última jornada)."""

import json
import os

import workday

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

DEFAULTS = {"focus_min": 25, "break_min": 5, "activities": True,
            "workday": list(workday.DEFAULT_TIMES)}
LIMITS = {"focus_min": (1, 180), "break_min": (1, 60)}


def clamp_minutes(key, value):
    low, high = LIMITS[key]
    return max(low, min(high, int(value)))


def _clean(key, value):
    if key == "workday":
        times = [int(v) for v in value]
        if not workday.valid_times(times):
            raise ValueError("jornada inválida")
        return times
    if key == "activities":
        if not isinstance(value, bool):
            raise ValueError("activities deve ser true/false")
        return value
    return clamp_minutes(key, value)


def _defaults():
    return {**DEFAULTS, "workday": list(DEFAULTS["workday"])}


def load(path=None):
    """Lê o arquivo; campo ausente ou inválido volta ao valor padrão."""
    values = _defaults()
    try:
        with open(path or PATH, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return values
    if not isinstance(data, dict):
        return values
    for key in DEFAULTS:
        try:
            values[key] = _clean(key, data[key])
        except (KeyError, ValueError, TypeError):
            pass
    return values


def save(values, path=None):
    """Atualiza só as chaves recebidas e devolve a configuração completa."""
    current = load(path)
    for key, value in values.items():
        if key in DEFAULTS:
            current[key] = _clean(key, value)
    with open(path or PATH, "w", encoding="utf-8") as fh:
        json.dump(current, fh, indent=2)
    return current
