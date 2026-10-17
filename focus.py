# focus.py — manual focus timer with idle pause, crash recovery, and reports
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from datetime import timedelta
from pathlib import Path

from clock import format_hms, local_date, parse_iso, today_local
from idle import pid_running, terminate_pid
from overlay import run_overlay
from session import (
    DEFAULT_IDLE_SECONDS,
    apply_stale_gap,
    filtered_sessions,
    finish_current,
    live_seconds,
    longest_session,
    new_current,
    recover_orphan,
    summarize,
    tick_session,
    week_start_local,
)
from storage import load_current, save_current


def print_recovered(record: dict) -> None:
    started = parse_iso(record["started_at"]).astimezone().strftime("%H:%M:%S")
    print(
        f"Recovered a session that ended when the timer crashed "
        f"(started {started}, {format_hms(record['duration_seconds'])})."
    )


def maybe_recover() -> None:
    record = recover_orphan()
    if record is not None:
        print_recovered(record)


def spawn_watcher() -> int:
    creationflags = 0
    if sys.platform == "win32":
        creationflags = (
            subprocess.CREATE_NO_WINDOW
            | subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NEW_PROCESS_GROUP
        )
    proc = subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "overlay"],
        cwd=str(Path(__file__).resolve().parent),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
        close_fds=True,
    )
    return proc.pid


def cmd_start(project: str | None, idle_threshold: int) -> None:
    maybe_recover()
    if load_current() is not None:
        raise RuntimeError("A session is already running. Stop it first.")
    current = new_current(project, idle_threshold)
    save_current(current)
    pid = spawn_watcher()
    current["pid"] = pid
    save_current(current)
    when = parse_iso(current["started_at"]).astimezone().strftime("%H:%M:%S")
    extra = f"  project={project}" if project else ""
    print(f"Focus started at {when}.{extra}")
    print(f"Idle pause after {idle_threshold} seconds without input.")
    print("A timer is in the bottom-right corner (drag to move).")
    print("Click stop on the overlay, or run:  python focus.py stop")


def cmd_status() -> None:
    maybe_recover()
    current = load_current()
    if current is None:
        print("No session running.")
        return
    current = apply_stale_gap(current)
    seconds = live_seconds(current)
    started = parse_iso(current["started_at"]).astimezone()
    state = "paused (idle)" if current.get("paused") else "running"
    project = current.get("project")
    print(f"{state.capitalize()}: {format_hms(seconds)}")
    print(f"Started: {started.strftime('%Y-%m-%d %H:%M:%S')}")
    if project:
        print(f"Project: {project}")


def cmd_stop(note: str | None) -> None:
    maybe_recover()
    current = load_current()
    if current is None:
        raise RuntimeError("No session is running.")
    pid = current.get("pid")
    terminate_pid(pid)
    for _ in range(20):
        if not pid_running(pid):
            break
        time.sleep(0.05)
    record = finish_current(note=note)
    line = f"Stopped. Total: {format_hms(record['duration_seconds'])}"
    if record.get("project"):
        line += f"  [{record['project']}]"
    print(line)


def _live_if_matches(day=None, week_from=None, project: str | None = None) -> int:
    current = load_current()
    if current is None:
        return 0
    if project is not None and (current.get("project") or "") != project:
        return 0
    started = local_date(parse_iso(current["started_at"]))
    if day is not None and started != day:
        return 0
    if week_from is not None and started < week_from:
        return 0
    return live_seconds(apply_stale_gap(current))


def _print_range(label: str, sessions: list[dict], live: int) -> None:
    total, count = summarize(sessions, live)
    print(f"{label}: {format_hms(total)}  ({count} saved session(s))")
    if live:
        print(f"Including running session: {format_hms(live)}")


def cmd_today(project: str | None) -> None:
    maybe_recover()
    day = today_local()
    sessions = filtered_sessions(since=day, until=day, project=project)
    _print_range("Today", sessions, _live_if_matches(day=day, project=project))


def cmd_yesterday(project: str | None) -> None:
    maybe_recover()
    day = today_local() - timedelta(days=1)
    sessions = filtered_sessions(since=day, until=day, project=project)
    _print_range("Yesterday", sessions, 0)


def cmd_week(project: str | None) -> None:
    maybe_recover()
    start = week_start_local()
    sessions = filtered_sessions(since=start, until=today_local(), project=project)
    _print_range("This week", sessions, _live_if_matches(week_from=start, project=project))


def cmd_longest(project: str | None) -> None:
    maybe_recover()
    session = longest_session(project=project)
    if session is None:
        print("No saved sessions yet.")
        return
    started = parse_iso(session["started_at"]).astimezone()
    project_name = session.get("project") or "-"
    print(
        f"Longest: {format_hms(session['duration_seconds'])}  "
        f"{started.strftime('%Y-%m-%d %H:%M')}  [{project_name}]"
    )


def cmd_list(limit: int, project: str | None) -> None:
    maybe_recover()
    sessions = filtered_sessions(project=project)
    if not sessions:
        print("No saved sessions yet.")
        return
    for session in sessions[-limit:]:
        started = parse_iso(session["started_at"]).astimezone()
        project_name = session.get("project") or "-"
        note = session.get("note")
        line = (
            f"{started.strftime('%Y-%m-%d %H:%M')}  "
            f"{format_hms(session['duration_seconds']):>8}  [{project_name}]"
        )
        if note:
            line += f"  {note}"
        print(line)


def cmd_overlay() -> None:
    if load_current() is None:
        raise RuntimeError("No session running. Start one first.")
    run_overlay()


def cmd_watch() -> None:
    me = os.getpid()
    while True:
        current = tick_session(me)
        if current is None:
            return
        time.sleep(1)


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "overlay":
        run_overlay()
        return
    if len(sys.argv) > 1 and sys.argv[1] == "watch":
        cmd_watch()
        return

    parser = argparse.ArgumentParser(description="Manual focus timer (no 25-minute cap)")
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start", help="start a focus session")
    start.add_argument("--project", "-p", help="optional project tag")
    start.add_argument(
        "--idle",
        type=int,
        default=DEFAULT_IDLE_SECONDS,
        help=f"idle seconds before pause (default {DEFAULT_IDLE_SECONDS})",
    )

    stop = sub.add_parser("stop", help="stop the running session")
    stop.add_argument("--note", "-n", help="optional note saved with the session")

    sub.add_parser("status", help="show live elapsed time")
    sub.add_parser("show", help="bring back the corner timer for a running session")

    for name, help_text in (
        ("today", "total focus time today"),
        ("yesterday", "total focus time yesterday"),
        ("week", "total focus time this week (Mon-today)"),
        ("longest", "longest saved session"),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--project", "-p", help="only this project tag")

    listing = sub.add_parser("list", help="print recent sessions")
    listing.add_argument("--limit", type=int, default=20)
    listing.add_argument("--project", "-p", help="only this project tag")

    args = parser.parse_args()

    try:
        if args.command == "start":
            if args.idle < 10:
                raise RuntimeError("Idle threshold must be at least 10 seconds.")
            cmd_start(args.project, args.idle)
        elif args.command == "stop":
            cmd_stop(args.note)
        elif args.command == "status":
            cmd_status()
        elif args.command == "show":
            cmd_overlay()
        elif args.command == "today":
            cmd_today(args.project)
        elif args.command == "yesterday":
            cmd_yesterday(args.project)
        elif args.command == "week":
            cmd_week(args.project)
        elif args.command == "longest":
            cmd_longest(args.project)
        elif args.command == "list":
            cmd_list(args.limit, args.project)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
