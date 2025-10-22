import os, time, pygame
print("SDL_AUDIODRIVER =", os.environ.get("SDL_AUDIODRIVER"))
try:
  pygame.mixer.pre_init(44100, -16, 2, 1024)
  pygame.mixer.init()
  print("[init] mixer =", pygame.mixer.get_init())
except Exception as e:
  print("[init] failed:", e)
  raise

def load_ok(path):
  import os
  print(f"[load] {path} exists?", os.path.exists(path))
  try:
    s = pygame.mixer.Sound(path)
    s.set_volume(0.8)
    print("[load] sound loaded OK")
    return s
  except Exception as e:
    print("[load] sound failed:", e)

s = load_ok("assets/correct.wav") or load_ok("assets/correct.ogg")
if s:
  print("[play] playing sfx…")
  s.play()
  time.sleep(2)

try:
  if os.path.exists("assets/theme.ogg"):
    pygame.mixer.music.load("assets/theme.ogg")
  else:
    pygame.mixer.music.load("assets/theme.wav")
  pygame.mixer.music.set_volume(0.6)
  pygame.mixer.music.play(-1)
  print("[play] music looping… 5s")
  time.sleep(5)
  pygame.mixer.music.stop()
except Exception as e:
  print("[music] failed:", e)

