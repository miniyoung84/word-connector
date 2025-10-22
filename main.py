"""
Chain Reaction — Final Round (Host + Display)

Quick, no-frills Python app with two windows:
- Display window: show the board (for screen sharing)
- Host window: control letters, guesses, sounds

Dependencies:
  - Python 3.9+
  - tkinter (bundled with Python on most OSes)
  - pygame (for sound)

Install:
  pip install pygame

Run:
  python main.py

Sound assets:
  Put your files in a folder like ./assets and update SOUND_FILES below.
  Missing files are handled gracefully (no crash; just no sound).

Author: Chase Choi
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox

# Optional: pygame for sound
try:
  import pygame
  pygame.mixer.pre_init(44100, -16, 2, 1024)
  pygame.mixer.init()
  pygame.mixer.music.set_volume(0.5)
  SOUND_OK = True
except Exception:
  SOUND_OK = False

APP_TITLE = "Chain Reaction — Final Round"

# ---- CONFIG ----
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
SOUND_FILES = {
  "correct": os.path.join(ASSETS_DIR, "correct.wav"),
  "wrong": os.path.join(ASSETS_DIR, "incorrect.wav"),
  "tick": os.path.join(ASSETS_DIR, "tick.wav"),  # optional letter-reveal sound
  # Background soundtrack for timer (looped while timer runs)
  "soundtrack": os.path.join(ASSETS_DIR, "theme.wav"),
  "last_letter": os.path.join(ASSETS_DIR, "ding.wav"),
}


# Fallback sample chain (edit in Host window before pressing "Load Chain")
SAMPLE_CHAIN = [
  "SOLAR",  
  "POWER",
  "PLANT", 
  "FOOD",
  "CHAIN", 
  "LINK", 
  "CARD"
]


# ---- SOUND HELPERS ----
class Sounder:
  def __init__(self):
    self.enabled = SOUND_OK
    self.cache = {}
    if self.enabled:
      for key, path in SOUND_FILES.items():
        if path and os.path.exists(path):
          try:
            self.cache[key] = pygame.mixer.Sound(path)
          except Exception:
            pass

  def play(self, key: str):
    if not self.enabled:
      return
    s = self.cache.get(key)
    if s is not None:
      try:
        s.play()
      except Exception:
        pass


# ---- GAME STATE ----
class GameState:
  def __init__(self, words: list[str]):
    if len(words) < 3:
      raise ValueError("Chain must have at least 3 words (top, middle..., bottom)")
    self.words = [w.strip().upper() for w in words]
    # first and last fully revealed; middle hidden
    self.revealed = []
    for i, w in enumerate(self.words):
      if i in (0, len(self.words) - 1):
        self.revealed.append([True] * len(w))
      else:
        self.revealed.append([False] * len(w))
    # Track when the final letter is intentionally withheld for a word
    self.withheld_last = [False] * len(self.words)

  def word_mask(self, idx: int) -> str:
    """
    Display logic:
      - Top and bottom show fully.
      - Middle words: show only the letters that are revealed; do NOT show blanks/underscores.
      - If the last letter was withheld, append a question mark at the end.
    This prevents revealing the total length of the word.
    """
    w = self.words[idx]
    flags = self.revealed[idx]
    if idx in (0, len(self.words) - 1):
      return w  # fully revealed ends

    # Only include revealed letters (no placeholders)
    shown_letters = [ch for ch, f in zip(w, flags) if f]
    s = "".join(shown_letters)
    # If we deliberately withheld the final letter (all but one revealed), show a question mark
    if self.withheld_last[idx] and not all(flags):
      if s:
        return s + " ?"
      else:
        return "?"
    return s

  def reveal_next_letter(self, idx: int) -> tuple[bool, bool]:
    """Reveal next hidden letter left-to-right for a middle row.
    Returns (revealed, withheld_last)
      - revealed=True when we actually flipped a hidden letter to visible
      - withheld_last=True when we *didn't* reveal because it was the last remaining letter
    """
    if idx in (0, len(self.words) - 1):
      return (False, False)
    flags = self.revealed[idx]
    hidden_positions = [i for i, f in enumerate(flags) if not f]
    if not hidden_positions:
      return (False, False)
    if len(hidden_positions) == 1:
      # Do NOT reveal the last letter; mark withheld and signal to UI
      self.withheld_last[idx] = True
      return (False, True)
    # Otherwise reveal the next leftmost hidden letter
    next_i = hidden_positions[0]
    flags[next_i] = True
    return (True, False)

  def is_word_complete(self, idx: int) -> bool:
    return all(self.revealed[idx])

  def try_guess(self, idx: int, guess: str) -> bool:
    """If guess matches, reveal whole word. Returns True if correct."""
    target = self.words[idx]
    if guess.strip().upper() == target:
      self.revealed[idx] = [True] * len(target)
      self.withheld_last[idx] = False
      return True
    return False


# ---- UI ----
class App:
  def __init__(self, root: tk.Tk):
    self.root = root
    self.root.title(APP_TITLE)
    self.sounder = Sounder()

    # Create display window (for screen share)
    self.display = tk.Toplevel(self.root)
    self.display.title("Display — Share this window")
    self.display.geometry("900x700")
    self.display.attributes("-topmost", False)

    # Fonts
    self.font_word = ("Arial", 36, "bold")
    self.font_small = ("Arial", 12)

    # Display layout
    self.display_frame = tk.Frame(self.display, bg="#111111")
    self.display_frame.pack(fill=tk.BOTH, expand=True)

    self.chain_frame = tk.Frame(self.display_frame, bg="#111111")
    self.chain_frame.pack(pady=20)

    self.info_label = tk.Label(
      self.display_frame,
      text="",
      fg="#AAAAAA",
      bg="#111111",
      font=self.font_small,
    )
    self.info_label.pack(pady=6)

    # Timer display on the Display window
    self.font_timer = ("Arial", 48, "bold")
    self.timer_label = tk.Label(
      self.display_frame,
      text="00:00",
      fg="#FFFFFF",
      bg="#111111",
      font=self.font_timer,
    )
    self.timer_label.pack(pady=10)

    # Host controls in root
    self._build_host_controls(self.root)

    # ---- Timer state (ensure these exist BEFORE any refresh_display call) ----
    self.timer_running = False
    self.timer_seconds = 60  # default
    self._timer_job = None

    # Initialize with sample chain
    self.game: GameState | None = None
    self.labels: list[tk.Label] = []
    self.load_chain_from_text("\n".join(SAMPLE_CHAIN))

  # ---- Host controls ----
  def _build_host_controls(self, parent: tk.Widget):
    parent.geometry("600x780")

    top = tk.Frame(parent)
    top.pack(fill=tk.X, padx=10, pady=10)

    tk.Label(top, text="Chain words (one per line). First and last are auto-revealed:").pack(anchor="w")
    self.chain_text = tk.Text(top, height=10, width=60)
    self.chain_text.pack(fill=tk.X)
    self.chain_text.insert("1.0", "\n".join(SAMPLE_CHAIN))

    ctl = tk.Frame(parent)
    ctl.pack(fill=tk.X, padx=10, pady=10)

    tk.Button(ctl, text="Load Chain", command=self._on_load_chain).grid(row=0, column=0, padx=4, pady=4, sticky="ew")
    tk.Button(ctl, text="Reset Reveals", command=self._on_reset_reveals).grid(row=0, column=1, padx=4, pady=4, sticky="ew")
    tk.Button(ctl, text="Toggle Fullscreen (Display)", command=self._on_toggle_fullscreen).grid(row=0, column=2, padx=4, pady=4, sticky="ew")

    row2 = tk.Frame(parent)
    row2.pack(fill=tk.X, padx=10, pady=10)
    tk.Label(row2, text="Select word index (for guesses):").grid(row=0, column=0, sticky="w")
    self.idx_var = tk.IntVar(value=1)
    self.idx_spin = tk.Spinbox(row2, from_=1, to=7, width=5, textvariable=self.idx_var)
    self.idx_spin.grid(row=0, column=1, padx=6)

    # Quick buttons to reveal letters at the nearest unsolved word above/below
    row2b = tk.Frame(parent)
    row2b.pack(fill=tk.X, padx=10, pady=4)
    tk.Button(row2b, text="LETTER BELOW", command=self._on_give_letter_above).grid(row=0, column=0, padx=4)
    tk.Button(row2b, text="LETTER ABOVE", command=self._on_give_letter_below).grid(row=0, column=1, padx=4)

    # Reveal WHOLE word above/below (no index)
    row2c = tk.Frame(parent)
    row2c.pack(fill=tk.X, padx=10, pady=4)
    tk.Button(row2c, text="BELOW CORRECT", command=self._on_reveal_word_above).grid(row=0, column=0, padx=4)
    tk.Button(row2c, text="ABOVE CORRECT", command=self._on_reveal_word_below).grid(row=0, column=1, padx=4)

    guess_row = tk.Frame(parent)
    guess_row.pack(fill=tk.X, padx=10, pady=10)
    tk.Label(guess_row, text="Guess:").grid(row=0, column=0, sticky="w")
    self.guess_entry = tk.Entry(guess_row, width=30)
    self.guess_entry.grid(row=0, column=1, padx=6)
    tk.Button(guess_row, text="Submit Guess", command=self._on_submit_guess).grid(row=0, column=2, padx=4)

    sound_row = tk.Frame(parent)
    sound_row.pack(fill=tk.X, padx=10, pady=10)
    # Only WRONG manual button (Correct plays automatically on reveal/guess)
    tk.Button(sound_row, text="Play WRONG", command=lambda: self.sounder.play("wrong")).grid(row=0, column=0, padx=4)

    # Timer controls
    timer_row = tk.LabelFrame(parent, text="Timer")
    timer_row.pack(fill=tk.X, padx=10, pady=10)
    tk.Label(timer_row, text="Seconds:").grid(row=0, column=0, sticky="w")
    self.timer_entry = tk.Entry(timer_row, width=8)
    self.timer_entry.insert(0, "60")
    self.timer_entry.grid(row=0, column=1, padx=6)
    tk.Button(timer_row, text="Start", command=self._on_timer_start).grid(row=0, column=2, padx=4)
    tk.Button(timer_row, text="Pause", command=self._on_timer_pause).grid(row=0, column=3, padx=4)
    tk.Button(timer_row, text="Reset", command=self._on_timer_reset).grid(row=0, column=4, padx=4)

    status = tk.Frame(parent)
    status.pack(fill=tk.X, padx=10, pady=10)
    self.status_var = tk.StringVar(value="Ready.")
    tk.Label(status, textvariable=self.status_var).pack(anchor="w")

  # ---- Event handlers ----
  def _on_toggle_fullscreen(self):
    cur = bool(self.display.attributes("-fullscreen"))
    self.display.attributes("-fullscreen", not cur)

  def _on_load_chain(self):
    text = self.chain_text.get("1.0", tk.END).strip()
    try:
      self.load_chain_from_text(text)
      self.status_var.set("Chain loaded.")
    except Exception as e:
      messagebox.showerror("Load Chain Failed", str(e))

  def _on_reset_reveals(self):
    if not self.game:
      return
    words = self.game.words
    self.game = GameState(words)
    self.refresh_display()
    self.status_var.set("Reveals reset.")

  def _on_give_letter(self):
    # Kept for index-based control; new convenience buttons below.
    if not self.game:
      return
    idx = self._safe_idx()
    if idx is None:
      return
    revealed, withheld = self.game.reveal_next_letter(idx)
    if revealed:
      self.refresh_display(highlight_idx=idx)
      self.sounder.play("tick")
      self.status_var.set(f"Gave a letter to word {idx}.")
      self._maybe_puzzle_solved()
    elif withheld:
      self.refresh_display(highlight_idx=idx)
      self.sounder.play("last_letter")
      self.status_var.set("Last letter withheld — ? shown.")
      self._maybe_puzzle_solved()
    else:
      self.status_var.set("No hidden letters left (or top/bottom word).")

  def _on_give_letter_above(self):
    """Reveal a letter on the topmost unsolved middle word (closest to the top)."""
    if not self.game:
      return
    idx = self._topmost_unsolved_idx()
    if idx is None:
      self.status_var.set("All middle words solved.")
      return
    revealed, withheld = self.game.reveal_next_letter(idx)
    if revealed:
      self.refresh_display(highlight_idx=idx)
      self.sounder.play("tick")
      self.status_var.set(f"Gave a letter (above) to word {idx}.")
      self._maybe_puzzle_solved()
    elif withheld:
      self.refresh_display(highlight_idx=idx)
      self.sounder.play("tick")
      self.status_var.set("Last letter withheld — ? shown (above).")
      self._maybe_puzzle_solved()
    else:
      self.status_var.set("No hidden letters left on that word.")

  def _on_give_letter_below(self):
    """Reveal a letter on the bottommost unsolved middle word (closest to the bottom)."""
    if not self.game:
      return
    idx = self._bottommost_unsolved_idx()
    if idx is None:
      self.status_var.set("All middle words solved.")
      return
    revealed, withheld = self.game.reveal_next_letter(idx)
    if revealed:
      self.refresh_display(highlight_idx=idx)
      self.sounder.play("tick")
      self.status_var.set(f"Gave a letter (below) to word {idx}.")
      self._maybe_puzzle_solved()
    elif withheld:
      self.refresh_display(highlight_idx=idx)
      self.sounder.play("tick")
      self.status_var.set("Last letter withheld — ? shown (below).")
      self._maybe_puzzle_solved()
    else:
      self.status_var.set("No hidden letters left on that word.")

  def _on_reveal_word_above(self):
    if not self.game:
      return
    idx = self._topmost_unsolved_idx()
    if idx is None:
      self.status_var.set("No unsolved middle words.")
      return
    self.game.revealed[idx] = [True] * len(self.game.words[idx])
    try:
      self.game.withheld_last[idx] = False
    except Exception:
      pass
    self.refresh_display(highlight_idx=idx)
    self.sounder.play("correct")
    self.status_var.set(f"Revealed (above) word {idx}.")
    self._maybe_puzzle_solved()

  def _on_reveal_word_below(self):
    if not self.game:
      return
    idx = self._bottommost_unsolved_idx()
    if idx is None:
      self.status_var.set("No unsolved middle words.")
      return
    self.game.revealed[idx] = [True] * len(self.game.words[idx])
    try:
      self.game.withheld_last[idx] = False
    except Exception:
      pass
    self.refresh_display(highlight_idx=idx)
    self.sounder.play("correct")
    self.status_var.set(f"Revealed (below) word {idx}.")
    self._maybe_puzzle_solved()

  def _on_submit_guess(self):
    if not self.game:
      return
    idx = self._safe_idx()
    if idx is None:
      return
    guess = self.guess_entry.get().strip()
    if not guess:
      return
    if idx in (0, len(self.game.words) - 1):
      self.status_var.set("Top/bottom are already revealed.")
      return
    ok = self.game.try_guess(idx, guess)
    if ok:
      self.refresh_display(highlight_idx=idx)
      self.sounder.play("correct")
      self.status_var.set(f"Correct! {self.game.words[idx]}")
      self._maybe_puzzle_solved()
      self.guess_entry.delete(0, tk.END)
    else:
      self.sounder.play("wrong")
      self.status_var.set("Nope. Keep trying.")

  def _topmost_unsolved_idx(self):
    """Return the smallest index of an unsolved middle word (1..n-2), or None."""
    if not self.game:
      return None
    for i in range(1, len(self.game.words) - 1):
      if not self.game.is_word_complete(i):
        return i
    return None

  def _bottommost_unsolved_idx(self):
    """Return the largest index of an unsolved middle word (n-2..1), or None."""
    if not self.game:
      return None
    for i in range(len(self.game.words) - 2, 0, -1):
      if not self.game.is_word_complete(i):
        return i
    return None

  def _safe_idx(self):
    try:
      idx = int(self.idx_var.get())
    except Exception:
      self.status_var.set("Invalid index")
      return None
    if not self.game:
      return None
    if idx < 0 or idx >= len(self.game.words):
      self.status_var.set("Index out of bounds")
      return None
    return idx

  # ---- Game wiring ----
  def load_chain_from_text(self, text: str):
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) < 3:
      raise ValueError("Provide at least 3 lines (top, middle..., bottom)")
    self.game = GameState(lines)
    # Reset spinbox bounds to chain length
    self.idx_spin.config(from_=0, to=len(lines) - 1)
    self.idx_var.set(1 if len(lines) > 2 else 0)
    self.build_display_labels()
    self.refresh_display()

  def build_display_labels(self):
    for w in self.chain_frame.winfo_children():
      w.destroy()
    self.labels = []
    if not self.game:
      return

    for i, _ in enumerate(self.game.words):
      row = tk.Frame(self.chain_frame, bg="#111111")
      row.pack(pady=6)
      lbl = tk.Label(
        row,
        text="",
        fg="#00FFCC" if i in (0, len(self.game.words) - 1) else "#FFFFFF",
        bg="#111111",
        font=self.font_word,
      )
      lbl.pack()
      self.labels.append(lbl)

  def refresh_display(self, highlight_idx: int | None = None):
    if not self.game:
      return
    for i, lbl in enumerate(self.labels):
      mask = self.game.word_mask(i)
      # Insert spaces between shown letters only (no placeholders)
      pretty = " ".join(list(mask)) if mask else ""
      lbl.config(text=pretty)
      if i == 0 or i == len(self.labels) - 1:
        lbl.config(fg="#00FFCC")
      else:
        lbl.config(fg="#FFFFFF")

    # Update timer label (guard if timer not inited yet)
    secs = getattr(self, "timer_seconds", 0)
    self.timer_label.config(text=self._format_seconds(secs))

    if highlight_idx is not None:
      self.info_label.config(text=f"Selected word: {highlight_idx+1} / {len(self.labels)}")
    else:
      self.info_label.config(text="")

  # ---- Timer helpers ----
  def _format_seconds(self, s: int) -> str:
    m = max(0, s) // 60
    sec = max(0, s) % 60
    return f"{m:02d}:{sec:02d}"

  def _render_timer(self):
    self.timer_label.config(text=self._format_seconds(self.timer_seconds))

  def _update_timer_tick(self):
    if not self.timer_running:
      return
    self.timer_seconds = max(0, self.timer_seconds - 1)
    self._render_timer()
    if self.timer_seconds == 0:
      # time's up
      self._on_timer_pause()
      self.sounder.play("wrong")
      self.status_var.set("Timer finished.")
      return
    # schedule next tick
    self._timer_job = self.root.after(1000, self._update_timer_tick)

  def _on_timer_start(self):
    try:
      val = int(self.timer_entry.get())
      if val > 0:
        self.timer_seconds = val
    except Exception:
      pass
    if not self.timer_running:
      self.timer_running = True
      self._render_timer()
      self._start_music()
      self._timer_job = self.root.after(1000, self._update_timer_tick)
      self.status_var.set("Timer started.")

  def _on_timer_pause(self):
    self.timer_running = False
    if self._timer_job is not None:
      try:
        self.root.after_cancel(self._timer_job)
      except Exception:
        pass
      self._timer_job = None
    self._pause_music()
    self.status_var.set("Timer paused.")

  def _on_timer_reset(self):
    # Keep current entry value as new base
    try:
      self.timer_seconds = int(self.timer_entry.get())
    except Exception:
      self.timer_seconds = 60
    self.timer_running = False
    if self._timer_job is not None:
      try:
        self.root.after_cancel(self._timer_job)
      except Exception:
        pass
      self._timer_job = None
    self._stop_music()
    self._render_timer()
    self.status_var.set("Timer reset.")

  def _start_music(self):
    if not SOUND_OK:
      return
    path = SOUND_FILES.get("soundtrack")
    if not (path and os.path.exists(path)):
      return
    try:
      pygame.mixer.music.load(path)
      pygame.mixer.music.play(-1)  # loop
    except Exception:
      pass

  def _pause_music(self):
    if not SOUND_OK:
      return
    try:
      pygame.mixer.music.pause()
    except Exception:
      pass

  def _stop_music(self):
    if not SOUND_OK:
      return
    try:
      pygame.mixer.music.stop()
    except Exception:
      pass

  def _is_puzzle_solved(self) -> bool:
    if not self.game:
      return False
    # all middle words complete
    for i in range(1, len(self.game.words) - 1):
      if not self.game.is_word_complete(i):
        return False
    return True

  def _maybe_puzzle_solved(self):
    if self._is_puzzle_solved():
      if self.timer_running:
        self._on_timer_pause()
      self.status_var.set("Puzzle solved! Timer paused.")


def main():
  root = tk.Tk()
  app = App(root)
  root.mainloop()


if __name__ == "__main__":
  main()
