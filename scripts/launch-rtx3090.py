"""Launches the title with this fork's settings, as measured on an RTX 3090.

    python scripts/launch-rtx3090.py --game=<dir>/game_scarlett_master.exe [options]

Options:
  --game=<file>       the title's game_scarlett_master.exe (required). Its folder's
                      parent must hold a `data` folder with the title's storage
                      (copied once into the state folder on first use).
  --exe=<file>        victory.exe to run (default: target/diag/victory.exe).
  --state=<dir>       where caches, the copied data and run logs go, outside the source
                      tree (default: %LOCALAPPDATA%\VIctory\rtx3090).
  --profile=<name>    series-s (default) or series-x.
  --diagnose          the diagnostics profile the measurements were made with
                      (frame captures on request, render-target dumps).
  --preset=user-env   the switches of the published candidate (see README):
                      VICTORY_THIN=0 VICTORY_PIPELINE_WAIT_MS=150 VICTORY_PIPELINE_WORKERS=6
                      VICTORY_PIPELINE_LOWEST=1 (and three switches only other forks read).
  --env=NAME=VALUE    any VICTORY_* switch (repeatable), applied last.
  --affinity=<mask>   process affinity, e.g. 0xffff for the P-cores of a 24-thread
                      Intel CPU (default: unchanged).
  --label=<text>      shown in front of the window title (default: "VIctory - <exe folder>").
  --no-exit-watchdog  do not end the process tree when its window is gone.

No game files, keys or dumps are included or provided: bring your own legally obtained copy.
"""
from pathlib import Path
from datetime import datetime
import ctypes as ct
import os, re, shutil, subprocess, sys, threading, time

repo = Path(__file__).resolve().parents[1]


def opt(name, default=None):
    return next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith(f"--{name}=")), default)


game = opt("game")
if not game:
    sys.exit(__doc__)
title = Path(game).resolve()
binary = Path(opt("exe", repo / "target" / "diag" / "victory.exe")).resolve()
# Game-derived output never goes below the source tree (.victory-root, docs/asset-policy.md).
state = Path(opt("state", Path(os.environ.get("LOCALAPPDATA", Path.home())) / "VIctory" / "rtx3090")).resolve()
if any((d / ".victory-root").exists() for d in [state, *state.parents]):
    sys.exit(f"--state={state} lies inside a VIctory source tree; choose a folder outside it")
profile = opt("profile", "series-s")
if profile not in {"series-x", "series-s"}:
    raise ValueError(profile)
diagnose = "--diagnose" in sys.argv[1:]
cache = state / "cache"
data = state / (profile + "-data")
state.mkdir(parents=True, exist_ok=True)
if not data.exists():
    shutil.copytree(title.parents[1] / "data", data)
folder = state / f"{profile}-{'diagnostic' if diagnose else 'run'}-{datetime.now():%Y%m%d-%H%M%S}"
(folder / "frames").mkdir(parents=True)

env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("VICTORY_", "RUST_LOG"))}
# The defaults of Play-VIctory.cmd (`if not defined VICTORY_X set "VICTORY_X=n"`).
preset = (repo / "Play-VIctory.cmd").read_text()
for name, value in re.findall(r'if not defined (VICTORY_\w+) set "(?:\1)=(\d+(?:\.\d+)?)"', preset):
    env[name] = value
env.update(VICTORY_GAME_DIR=str(title.parent), VICTORY_CACHE_DIR=str(cache), VICTORY_DATA_DIR=str(data),
           VICTORY_LOG="info,victory_gpu::descriptor=error,victory_gpu::pipeline=warn",
           VICTORY_WINDOW_MAX="1280x720", VICTORY_D3D12_DRED="faults",
           VICTORY_CAPTURE=str(folder / "frames"), VICTORY_CAPTURE_WORLD="1", VICTORY_CAPTURE_WORLD_ALSO="20,60",
           NO_COLOR="1")
if diagnose:
    env.update(VICTORY_CAPTURE_ON_REQUEST="1", VICTORY_DUMP_TARGETS="1", VICTORY_CAPTURE_TIMELINE="0",
               VICTORY_CAPTURE_WORLD_ALSO="144,208", VICTORY_DUMP_WORLD_OFFSETS="")
if opt("preset") == "user-env":
    env.update(VICTORY_THIN="0", VICTORY_PIPELINE_WAIT_MS="150", VICTORY_PIPELINE_WORKERS="6",
               VICTORY_PIPELINE_LOWEST="1",
               # Read only by other forks; kept so the set is the one measured.
               VICTORY_SKIP_WC_BACK="0", VICTORY_SKIP_WC_COMPARE="0", VICTORY_UP_QUEUE="1")
for a in sys.argv[1:]:
    if a.startswith("--env=") and "=" in a[6:]:
        k, v = a[6:].split("=", 1)
        env[k] = v

(folder / "env.txt").write_text(
    f"binary={binary}\nargs={' '.join(sys.argv[1:])}\n"
    + "".join(f"{k}={v}\n" for k, v in sorted(env.items()) if k.startswith(("VICTORY_", "NO_COLOR"))),
    encoding="utf-8")

k32 = ct.WinDLL("kernel32", use_last_error=True)
mask = opt("affinity")
if mask:
    if not k32.SetProcessAffinityMask(ct.c_void_p(-1), ct.c_size_t(int(mask, 0))):
        raise ct.WinError(ct.get_last_error())

label = opt("label", f"VIctory - {binary.parent.name}")
prefix = f"{label} | "

with (folder / "stdout.log").open("wb") as out, (folder / "stderr.log").open("wb") as err:
    p = subprocess.Popen([str(binary), "run", str(title), "--console", profile, "--execute"],
                         cwd=repo, env=env, stdout=out, stderr=err)
    print(folder, f"pid={p.pid}", flush=True)
    u = ct.WinDLL("user32", use_last_error=True)
    u.GetWindowTextW.argtypes = [ct.c_void_p, ct.c_wchar_p, ct.c_int]
    u.SetWindowTextW.argtypes = [ct.c_void_p, ct.c_wchar_p]
    u.GetWindowThreadProcessId.argtypes = [ct.c_void_p, ct.c_void_p]
    u.IsWindowVisible.argtypes = [ct.c_void_p]
    u.GetWindow.argtypes = [ct.c_void_p, ct.c_uint]
    u.GetWindow.restype = ct.c_void_p
    enum_proc = ct.WINFUNCTYPE(ct.c_bool, ct.c_void_p, ct.c_void_p)

    def windows():
        found = []

        def each(hwnd, _):
            owner = ct.c_ulong()
            u.GetWindowThreadProcessId(hwnd, ct.byref(owner))
            if owner.value == p.pid and u.IsWindowVisible(hwnd) and not u.GetWindow(hwnd, 4):
                buf = ct.create_unicode_buffer(512)
                u.GetWindowTextW(hwnd, buf, 512)
                found.append((hwnd, buf.value))
            return True

        u.EnumWindows(enum_proc(each), None)
        return found

    # The game rewrites its title once a second (frame rate): the label is put
    # back in front whenever it is missing. The title keeps running (and
    # playing audio) for a minute or more after its window is closed: once a
    # window was seen and then gone for 5 s, the process tree is ended.
    seen, gone_since = False, None
    while p.poll() is None:
        time.sleep(0.25)
        try:
            shown = windows()
        except OSError:
            continue
        for hwnd, text in shown:
            if text and not text.startswith(prefix):
                u.SetWindowTextW(hwnd, prefix + text)
        if any("Americas" in t for _, t in shown):
            seen, gone_since = True, None
        elif seen and "--no-exit-watchdog" not in sys.argv[1:]:
            gone_since = gone_since or time.monotonic()
            if time.monotonic() - gone_since >= 5:
                subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)
                break
    rc = p.wait()
    print(f"exit=0x{rc & 0xffffffff:08x}", flush=True)
