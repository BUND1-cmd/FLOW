from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CURRENT_PATH = ROOT / "current.json"
SESSIONS_PATH = ROOT / "sessions.json"


def load_json(path: Path, default):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_current() -> dict | None:
    data = load_json(CURRENT_PATH, None)
    if data is not None and not isinstance(data, dict):
        raise RuntimeError("current.json is invalid. Delete it if the timer is stuck.")
    return data


def save_current(data: dict) -> None:
    save_json(CURRENT_PATH, data)


def clear_current() -> None:
    if CURRENT_PATH.exists():
        CURRENT_PATH.unlink()


def load_sessions() -> list[dict]:
    data = load_json(SESSIONS_PATH, [])
    if not isinstance(data, list):
        raise RuntimeError("sessions.json is not a list. Fix or delete the file.")
    return data


def save_sessions(sessions: list[dict]) -> None:
    save_json(SESSIONS_PATH, sessions)


def append_session(record: dict) -> None:
    sessions = load_sessions()
    sessions.append(record)
    save_sessions(sessions)
