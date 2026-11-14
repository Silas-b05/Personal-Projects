"""Browser drafts, separate from confirmed Turso records."""
import json
import math

from nicegui import ui


async def read_drafts(scope: str) -> dict:
    return await ui.run_javascript(
        f'window.workoutDrafts.read({json.dumps(scope)})', timeout=10,
    ) or {}


def remember(element, key: str) -> None:
    element.on('update:model-value', js_handler=(
        f'(value) => window.workoutDrafts.put({json.dumps(key)}, value)'
    ))


def number_value(drafts: dict, key: str, fallback):
    if key not in drafts:
        return fallback
    value = drafts[key].get('value')
    if value is None or value == '':
        return None
    try:
        number = float(value)
        return number if math.isfinite(number) else fallback
    except (TypeError, ValueError):
        return fallback


async def acknowledge(drafts: dict) -> None:
    await ui.run_javascript(
        f'window.workoutDrafts.acknowledge({json.dumps(drafts)})', timeout=10,
    )
