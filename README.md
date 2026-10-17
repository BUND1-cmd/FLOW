# FLOW

A clocklike flow station that tracks how long you have sat down and focused on your computer. You start it, it runs until you stop it, and it keeps a history. There is no 25-minute cap.

Idle time (no mouse or keyboard) is paused. Sleep and crashes do not count as focus.

## Commands

```powershell
python focus.py start
python focus.py start --project thesis
python focus.py show
python focus.py status
python focus.py stop
python focus.py stop --note "chapter 2"

python focus.py today
python focus.py yesterday
python focus.py week
python focus.py longest
python focus.py list
```

Filter reports with `--project`:

```powershell
python focus.py today --project thesis
python focus.py week -p thesis
```

Idle pause defaults to **3 minutes**. Change it per session:

```powershell
python focus.py start --idle 120
```

## Files

| File | Role |
|---|---|
| `current.json` | The session in progress (heartbeat, pause state) |
| `sessions.json` | Finished sessions |

Times are stored in UTC and shown in your local timezone. A session counts on the **local date it started**.

## How it behaves

- `start` opens a small always-on-top timer in the **bottom-right** corner. Drag it if you want. Click **stop** on it to end the session.
- You can close the terminal; the corner timer keeps running.
- `python focus.py show` brings the overlay back if it disappeared while a session is still running.
- After 3 minutes idle, the current slice pauses at the last input.
- When you use the computer again, it resumes.
- If the watcher dies, the next command saves the session at the last heartbeat.
- Laptop sleep is a heartbeat gap, so that time is not counted.
