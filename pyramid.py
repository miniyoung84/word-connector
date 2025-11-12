# pyramid.py
# $100,000 Pyramid-style helper (Host Control + Display)
# - Display reveals prompts sequentially (#1 -> #2 -> ...).
# - Silent timer (visual only).
# - Finale shows a banner BELOW the timer (no overlap) and flashes cards lightly.
# - Host can pre-type all 6; only the current "Correct" button is enabled.

import threading
import time
import tkinter as tk
from tkinter import ttk
from dataclasses import dataclass, field

# Optional Windows sound backend
try:
  import winsound  # Windows only
  HAS_WINSOUND = True
except Exception:
  HAS_WINSOUND = False


def play_correct_sound():
  if HAS_WINSOUND:
    try:
      winsound.Beep(880, 100)
      winsound.Beep(1175, 140)
      return
    except Exception:
      pass
  root = tk._default_root
  if root:
    root.bell()


def play_win_sound():
  if HAS_WINSOUND:
    try:
      for f, d in [(700, 120), (900, 120), (1150, 180), (1400, 220)]:
        winsound.Beep(f, d)
        time.sleep(0.05)
      return
    except Exception:
      pass
  root = tk._default_root
  if root:
    for _ in range(3):
      root.bell()
      time.sleep(0.15)


@dataclass
class GameState:
  prompts: list[str] = field(default_factory=lambda: [""] * 6)
  correct: list[bool] = field(default_factory=lambda: [False] * 6)
  remaining_seconds: int = 60
  timer_running: bool = False
  reveal_upto: int = 0  # visible indices: 0..reveal_upto

  def all_correct(self) -> bool:
    return all(self.correct)

  def current_index(self) -> int:
    for i, ok in enumerate(self.correct):
      if not ok:
        return i
    return -1


class DisplayWindow(tk.Toplevel):
  def __init__(self, master, state: GameState):
    super().__init__(master)
    self.state = state
    self.title("Pyramid – Display")
    self.configure(bg="#0d0f12")
    self.geometry("900x600")
    self.minsize(700, 500)

    # Timer (visual only)
    self.timer_label = tk.Label(
      self, text="01:00", font=("Helvetica", 48, "bold"),
      fg="#e8e8e8", bg="#0d0f12"
    )
    self.timer_label.pack(pady=(16, 8))

    # *** NEW: Non-overlapping finale banner (initially hidden) ***
    self.win_banner = tk.Label(
      self, text="ALL SIX!", font=("Helvetica", 56, "bold"),
      fg="#00ffaa", bg="#0d0f12"
    )
    # We will pack/unpack this so it doesn’t overlay anything.

    # Grid for six prompts (progressively revealed)
    grid = tk.Frame(self, bg="#0d0f12")
    grid.pack(expand=True, fill="both", padx=16, pady=16)

    self.cards, self.card_labels = [], []
    for i in range(6):
      frame = tk.Frame(grid, bg="#0d0f12", highlightthickness=2, highlightbackground="#2b3139")
      r, c = divmod(i, 3)
      frame.grid(row=r, column=c, sticky="nsew", padx=10, pady=10)
      grid.grid_columnconfigure(c, weight=1)
      grid.grid_rowconfigure(r, weight=1)

      label = tk.Label(
        frame, text="", wraplength=260, justify="center",
        font=("Helvetica", 20, "bold"), fg="#e8e8e8", bg="#1a1e24"
      )
      label.pack(expand=True, fill="both", padx=12, pady=12)

      self.cards.append(frame)
      self.card_labels.append(label)

    self.flash_job = None
    self.refresh_view()

  def set_timer(self, seconds: int, urgent: bool = False):
    seconds = max(0, int(seconds))
    m, s = divmod(seconds, 60)
    self.timer_label.config(text=f"{m:02d}:{s:02d}", fg=("#ff5a5a" if urgent else "#e8e8e8"))

  def set_prompts(self, prompts):
    self.state.prompts = prompts[:]
    self.refresh_view()

  def set_correct(self, index, value):
    self.state.correct[index] = bool(value)
    self.refresh_view()

  def set_reveal_upto(self, upto_idx: int):
    self.state.reveal_upto = max(0, min(5, int(upto_idx)))
    self.refresh_view()

  def refresh_view(self):
    prompts = self.state.prompts
    # Hide everything first
    for i in range(6):
      self.cards[i].configure(bg="#0d0f12", highlightbackground="#0d0f12")
      self.card_labels[i].configure(text="", bg="#0d0f12")

    visible_last = self.state.reveal_upto
    for i in range(visible_last + 1):
      frame = self.cards[i]
      label = self.card_labels[i]
      solved = self.state.correct[i]
      text = prompts[i].strip() or f"Prompt {i+1}"

      if solved:
        frame.configure(bg="#12301f", highlightbackground="#22c55e")
        label.configure(text=f"✓ {text}", bg="#12301f", fg="#22f07a")
      else:
        frame.configure(bg="#1a1e24", highlightbackground="#2b3139")
        label.configure(text=text, bg="#1a1e24", fg="#e8e8e8")

  # ---------- Finale (banner below timer, no overlay) ----------
  def show_all_six(self):
    # Pack the banner directly under the timer so it doesn't cover tiles.
    # If it's already packed, re-pack to ensure position.
    try:
      self.win_banner.pack_forget()
    except Exception:
      pass
    self.win_banner.pack(after=self.timer_label, pady=(0, 8))
    self._start_flash()
    self.after(4000, self.hide_win_banner)

  def hide_win_banner(self):
    try:
      self.win_banner.pack_forget()
    except Exception:
      pass
    self._stop_flash()

  def _start_flash(self):
    if self.flash_job:
      return
    self._flash_tick()

  def _flash_tick(self):
    # Pulse the borders of visible cards
    for i in range(self.state.reveal_upto + 1):
      frame = self.cards[i]
      current = frame.cget("highlightbackground")
      frame.configure(highlightbackground="#00ffaa" if current != "#00ffaa" else "#22c55e")
    self.flash_job = self.after(180, self._flash_tick)

  def _stop_flash(self):
    if self.flash_job:
      self.after_cancel(self.flash_job)
      self.flash_job = None
    for i in range(self.state.reveal_upto + 1):
      frame = self.cards[i]
      # Keep green outline for solved, neutral for the current/others
      solved = self.state.correct[i]
      frame.configure(highlightbackground="#22c55e" if solved else "#2b3139")


class HostWindow(ttk.Frame):
  def __init__(self, master, state, display):
    super().__init__(master)
    self.master, self.state, self.display = master, state, display
    self.pack(fill="both", expand=True)
    self.master.title("Pyramid – Host Control")
    self.master.geometry("720x700")

    # Timer controls (visual only; no sounds)
    top = ttk.Frame(self)
    top.pack(fill="x", padx=12, pady=10)
    ttk.Label(top, text="Seconds:").pack(side="left")
    self.seconds_var = tk.IntVar(value=self.state.remaining_seconds)
    ttk.Spinbox(top, from_=10, to=180, width=5, textvariable=self.seconds_var).pack(side="left", padx=(6, 12))
    ttk.Button(top, text="Start Timer", command=self.start_timer).pack(side="left", padx=6)
    ttk.Button(top, text="Stop Timer", command=self.stop_timer).pack(side="left", padx=6)
    ttk.Button(top, text="Reset Timer", command=self.reset_timer).pack(side="left", padx=6)

    # Prompts + Correct buttons
    self.entry_vars = [tk.StringVar() for _ in range(6)]
    self.correct_btns = []
    grid = ttk.Frame(self)
    grid.pack(fill="both", expand=True, padx=12, pady=6)

    for i in range(6):
      row = ttk.Frame(grid)
      row.grid(row=i, column=0, sticky="ew", pady=6)
      ttk.Label(row, text=f"{i+1}.").pack(side="left", padx=(0, 8))
      ttk.Entry(row, textvariable=self.entry_vars[i]).pack(side="left", fill="x", expand=True)
      btn = ttk.Button(row, text="Correct", command=lambda idx=i: self.mark_correct(idx))
      btn.pack(side="left", padx=8)
      self.correct_btns.append(btn)

    # Controls
    bottom = ttk.Frame(self)
    bottom.pack(fill="x", padx=12, pady=10)
    ttk.Button(bottom, text="Send to Display", command=self.send_to_display).pack(side="left")
    ttk.Button(bottom, text="Clear Entries", command=self.clear_entries).pack(side="left", padx=8)
    ttk.Button(bottom, text="Unmark & Reset", command=self.unmark_all).pack(side="left", padx=8)

    self.status_var = tk.StringVar(value="Ready.")
    ttk.Label(self, textvariable=self.status_var, anchor="w").pack(fill="x", padx=12, pady=(0, 10))

    # Init
    self._tick_job = None
    self.send_to_display()
    self.display.set_timer(self.state.remaining_seconds)
    self._refresh_buttons()

  # --- Host actions ---
  def send_to_display(self):
    prompts = [v.get() for v in self.entry_vars]
    self.state.prompts = prompts
    cur = self.state.current_index()
    self.state.reveal_upto = (cur if cur >= 0 else 5)
    self.display.set_prompts(prompts)
    self.display.set_reveal_upto(self.state.reveal_upto)
    self.status_var.set("Prompts updated. Display reveals them in order.")
    self._refresh_buttons()

  def clear_entries(self):
    for v in self.entry_vars:
      v.set("")
    self.send_to_display()

  def unmark_all(self):
    self.state.correct = [False] * 6
    self.state.reveal_upto = 0
    self.display.hide_win_banner()
    self.display.refresh_view()
    self._refresh_buttons()
    self.status_var.set("Reset: back to prompt #1.")

  def mark_correct(self, idx):
    cur = self.state.current_index()
    if cur == -1:
      return
    if idx != cur:
      self.status_var.set(f"Only Prompt {cur+1} is active right now.")
      return

    if not self.state.correct[idx]:
      self.state.correct[idx] = True
      if idx < 5:
        self.state.reveal_upto = max(self.state.reveal_upto, idx + 1)
      self.display.set_correct(idx, True)
      self.display.set_reveal_upto(self.state.reveal_upto)
      threading.Thread(target=play_correct_sound, daemon=True).start()

      if self.state.all_correct():
        self._do_all_six()
      else:
        self._refresh_buttons()
        self.status_var.set(f"Correct! Now revealing Prompt {idx+2}.")

  # --- Timer management (visual only) ---
  def start_timer(self):
    if self.state.timer_running:
      return
    self.state.remaining_seconds = max(0, int(self.seconds_var.get()))
    self.state.timer_running = True
    self.display.set_timer(self.state.remaining_seconds)
    self._tick()

  def stop_timer(self):
    self.state.timer_running = False

  def reset_timer(self):
    self.stop_timer()
    self.state.remaining_seconds = max(0, int(self.seconds_var.get()))
    self.display.set_timer(self.state.remaining_seconds)
    self.status_var.set("Timer reset.")

  def _tick(self):
    if not self.state.timer_running:
      return
    self.state.remaining_seconds -= 1
    self.display.set_timer(self.state.remaining_seconds, urgent=self.state.remaining_seconds <= 10)
    if self.state.remaining_seconds <= 0:
      self.state.timer_running = False
      self.display.timer_label.config(text="TIME!", fg="#ff5a5a")
      self.status_var.set("Time's up!")
      return
    self._tick_job = self.after(1000, self._tick)

  # --- Finale ---
  def _do_all_six(self):
    self.stop_timer()
    self._refresh_buttons()
    self.display.show_all_six()
    threading.Thread(target=play_win_sound, daemon=True).start()
    self.status_var.set("ALL SIX! Round complete.")

  # --- Helpers ---
  def _refresh_buttons(self):
    cur = self.state.current_index()
    for i, btn in enumerate(self.correct_btns):
      if cur == -1:
        btn.state(["disabled"])
      elif i == cur:
        btn.state(["!disabled"])
      else:
        btn.state(["disabled"])


def main():
  root = tk.Tk()
  root.withdraw()
  state = GameState()
  display = DisplayWindow(root, state)
  host_root = tk.Toplevel(root)
  HostWindow(host_root, state, display)
  root.mainloop()


if __name__ == "__main__":
  main()
