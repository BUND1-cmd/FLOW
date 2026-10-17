from __future__ import annotations

import os
import tkinter as tk

from clock import format_hms
from session import finish_current, live_seconds, tick_session
from storage import load_current

BG = "#1b1b1f"
FG = "#e8e8ed"
MUTED = "#9a9aa8"
ACCENT = "#7dce82"
PAUSED = "#e6a23c"
WIDTH = 196
HEIGHT = 92


def _place_bottom_right(root: tk.Tk) -> None:
    root.update_idletasks()
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    x = screen_w - WIDTH - 18
    y = screen_h - HEIGHT - 56
    root.geometry(f"{WIDTH}x{HEIGHT}+{x}+{y}")


def run_overlay() -> None:
    root = tk.Tk()
    root.title("Focus")
    root.configure(bg=BG)
    root.resizable(False, False)
    root.attributes("-topmost", True)
    try:
        root.attributes("-toolwindow", True)
    except tk.TclError:
        pass
    root.overrideredirect(True)
    _place_bottom_right(root)

    drag = {"x": 0, "y": 0}

    def on_press(event) -> None:
        drag["x"] = event.x_root - root.winfo_x()
        drag["y"] = event.y_root - root.winfo_y()

    def on_drag(event) -> None:
        root.geometry(f"+{event.x_root - drag['x']}+{event.y_root - drag['y']}")

    time_label = tk.Label(
        root, text="0:00:00", fg=ACCENT, bg=BG, font=("Segoe UI", 22, "bold")
    )
    state_label = tk.Label(root, text="focus", fg=MUTED, bg=BG, font=("Segoe UI", 9))
    stop_btn = tk.Label(
        root, text="stop", fg=FG, bg="#2c2c34", font=("Segoe UI", 9), padx=10, pady=2
    )

    time_label.pack(pady=(10, 0))
    state_label.pack()
    stop_btn.pack(pady=(4, 8))

    for widget in (root, time_label, state_label):
        widget.bind("<ButtonPress-1>", on_press)
        widget.bind("<B1-Motion>", on_drag)

    stopping = {"done": False}

    def stop_session(_event=None) -> None:
        if stopping["done"]:
            return
        stopping["done"] = True
        if load_current() is not None:
            finish_current()
        root.destroy()

    stop_btn.bind("<Button-1>", stop_session)
    root.protocol("WM_DELETE_WINDOW", stop_session)

    def tick() -> None:
        current = tick_session(os.getpid())
        if current is None:
            root.destroy()
            return
        paused = bool(current.get("paused"))
        time_label.config(
            text=format_hms(live_seconds(current)),
            fg=PAUSED if paused else ACCENT,
        )
        project = current.get("project")
        if paused:
            state_label.config(text="paused  ·  idle")
        elif project:
            state_label.config(text=str(project))
        else:
            state_label.config(text="focus")
        root.after(1000, tick)

    tick()
    root.mainloop()
