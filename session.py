from __future__ import annotations

from datetime import datetime, timedelta

from clock import local_date, now_utc, parse_iso, today_local
from idle import idle_seconds, pid_running
from storage import append_session, clear_current, load_current, load_sessions, save_current

DEFAULT_IDLE_SECONDS = 180
STALE_HEARTBEAT_SECONDS = 90
ACTIVE_IDLE = 2.0


def new_current(project: str | None, idle_threshold: int, pid: int | None = None) -> dict:
    started = now_utc()
    stamp = started.isoformat()
    return {
        "started_at": stamp,
        "project": project,
        "pid": pid,
        "paused": False,
        "accumulated_seconds": 0,
        "slice_started_at": stamp,
        "last_heartbeat": stamp,
        "idle_threshold_seconds": idle_threshold,
    }


def live_seconds(current: dict, at: datetime | None = None) -> int:
    at = at or now_utc()
    total = int(current.get("accumulated_seconds") or 0)
    if not current.get("paused") and current.get("slice_started_at"):
        started = parse_iso(current["slice_started_at"])
        total += max(0, int((at - started).total_seconds()))
    return total


def pause_at(current: dict, at: datetime) -> dict:
    if current.get("paused"):
        return current
    extra = 0
    if current.get("slice_started_at"):
        extra = max(0, int((at - parse_iso(current["slice_started_at"])).total_seconds()))
    current["accumulated_seconds"] = int(current.get("accumulated_seconds") or 0) + extra
    current["paused"] = True
    current["slice_started_at"] = None
    return current


def resume_at(current: dict, at: datetime) -> dict:
    if not current.get("paused"):
        return current
    current["paused"] = False
    current["slice_started_at"] = at.isoformat()
    return current


def apply_stale_gap(current: dict, at: datetime | None = None) -> dict:
    """Do not count time while the watcher was frozen (sleep) or dead (crash)."""
    at = at or now_utc()
    heartbeat = parse_iso(current["last_heartbeat"])
    if (at - heartbeat).total_seconds() <= STALE_HEARTBEAT_SECONDS:
        return current
    return pause_at(current, heartbeat)


def heartbeat(current: dict, at: datetime | None = None) -> dict:
    at = at or now_utc()
    current["last_heartbeat"] = at.isoformat()
    return current


def to_record(current: dict, ended_at: datetime | None = None, note: str | None = None) -> dict:
    ended_at = ended_at or now_utc()
    current = apply_stale_gap(current, ended_at)
    if not current.get("paused"):
        pause_at(current, ended_at)
    started = parse_iso(current["started_at"])
    record = {
        "started_at": started.isoformat(),
        "ended_at": ended_at.isoformat(),
        "duration_seconds": int(current.get("accumulated_seconds") or 0),
        "project": current.get("project"),
        "note": note,
    }
    return record


def tick_session(owner_pid: int) -> dict | None:
    """Advance idle pause and heartbeat. None means the session is gone."""
    current = load_current()
    if current is None:
        return None
    owner = current.get("pid")
    if owner and owner != owner_pid and pid_running(owner):
        return None
    current["pid"] = owner_pid
    at = now_utc()
    current = apply_stale_gap(current, at)
    threshold = int(current.get("idle_threshold_seconds") or DEFAULT_IDLE_SECONDS)
    idle = idle_seconds()
    if not current.get("paused") and idle >= threshold:
        pause_time = at - timedelta(seconds=idle)
        slice_start = current.get("slice_started_at")
        if slice_start:
            started = parse_iso(slice_start)
            if pause_time < started:
                pause_time = started
        current = pause_at(current, pause_time)
    elif current.get("paused") and idle < ACTIVE_IDLE:
        current = resume_at(current, at)
    current = heartbeat(current, at)
    save_current(current)
    return current


def finish_current(note: str | None = None) -> dict:
    current = load_current()
    if current is None:
        raise RuntimeError("No session is running.")
    record = to_record(current, note=note)
    append_session(record)
    clear_current()
    return record


def recover_orphan() -> dict | None:
    """If the watcher died, save the session at the last heartbeat and clear it."""
    current = load_current()
    if current is None:
        return None
    current = apply_stale_gap(current)
    if pid_running(current.get("pid")):
        save_current(current)
        return None
    heartbeat_at = parse_iso(current["last_heartbeat"])
    if (now_utc() - heartbeat_at).total_seconds() < STALE_HEARTBEAT_SECONDS:
        save_current(current)
        return None
    record = to_record(current, ended_at=heartbeat_at)
    append_session(record)
    clear_current()
    return record


def session_on_local_day(session: dict, day) -> bool:
    return local_date(parse_iso(session["started_at"])) == day


def week_start_local():
    today = today_local()
    return today - timedelta(days=today.weekday())


def summarize(sessions: list[dict], live: int = 0) -> tuple[int, int]:
    total = sum(int(s.get("duration_seconds") or 0) for s in sessions) + live
    return total, len(sessions)


def filtered_sessions(since=None, until=None, project: str | None = None) -> list[dict]:
    out = []
    for session in load_sessions():
        started = local_date(parse_iso(session["started_at"]))
        if since is not None and started < since:
            continue
        if until is not None and started > until:
            continue
        if project is not None and (session.get("project") or "") != project:
            continue
        out.append(session)
    return out


def longest_session(project: str | None = None) -> dict | None:
    sessions = filtered_sessions(project=project)
    if not sessions:
        return None
    return max(sessions, key=lambda s: int(s.get("duration_seconds") or 0))
