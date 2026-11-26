# VIctory-RTX3090

A fork of [cool_fox](https://github.com/codec-d/cool_fox) (commit `f4b48ad`), which is itself a
fork of [VIctory](https://github.com/Marvisak/VIctory). VIctory is a compatibility layer that
runs an Xbox Series title natively on Windows from files the user supplies. This fork is tuned
and tested on an **NVIDIA RTX 3090**. It is shared so that others can help with the issues
listed below.

Licensed under **GPL-3.0-or-later**, like its upstreams (see `LICENSE`). All credit for the
compatibility layer goes to the VIctory and cool_fox authors and contributors. The upstream
README is kept unchanged as `UPSTREAM-README.md`.

**No game files, keys or dumps are included or provided.** You need your own legally obtained
copy of the game. This project is not affiliated with or endorsed by the game's developer or
publisher.

## What this fork changes (against cool_fox f4b48ad)

On by default:

- **Depth planes drawn from the twin mid-list (`planes_now`)**, with review fixes:
  - the depth target goes back to SHADER_RESOURCE after the early pass;
  - an 8,192-view ring;
  - a plane counts only when it was drawn;
  - a failure is warned about once.
  - `VICTORY_PLANES_NOW=0` turns it off.
- **Small textures rechecked:**
  - A small texture picked by index (up to 2 MiB) is fingerprinted whole.
  - It is looked at again every 30 frames after its scheduled looks.
  - Small textures read through tables are looked at again too, and at the next present while they keep changing (this fixed colour banding from grading tables the title rewrites unseen).
  - All of these looks share a budget of 16 MiB per 60 ms.
  - `VICTORY_SMALL_RECHECK=0` turns it off; `VICTORY_SMALL_RECHECK_MIB=<n>` sets the size limit.
- **Exit fix:** WM_CLOSE / WM_DESTROY on the title's shown window ends the title, so it no longer keeps running and playing audio for a minute after the window closes.

Experiment switches, all off by default (measured; none kept on):

- `VICTORY_FILL_TITLE=1` / `VICTORY_FILL_QUIET=<n>`: let some CPU constant fills through early. Faster waits, but banding.
- `VICTORY_GUARD_PRIVATE=1`: adopt private title ranges into the write guards. About 4 ms faster, but a shadow patch and banding.
- `VICTORY_PLACED_ORDER=1`: order placed copies differently on the card.
- `VICTORY_HELPERS_ECORES=1`: helper threads on the E-cores. About 10 ms slower.
- `VICTORY_GPU_LOAD_MS`, `VICTORY_BARRIER_TEST`, `VICTORY_TIMELINE`: diagnostics only (timing and traces). `VICTORY_BARRIER_TEST` removes ordering and is not a speed-up.

## Build

Windows x64, the pinned Rust toolchain (`rust-toolchain.toml`), the MSVC C++ build tools and a
Windows SDK.

```powershell
cargo build --locked --profile diag -p victory --features diagnostics   # the build all measurements are of
cargo build --locked --release -p victory                               # without diagnostics
```

## Run: the exact settings of the published build

The published build is the run the tester picked as best looking. Its launch is:

```powershell
python scripts\launch-rtx3090.py --game=<your copy>\game_scarlett_master.exe --exe=target\diag\victory.exe --diagnose --preset=user-env --affinity=0xffff
```

- **Profile:** Series S. Window at most 1280x720.
- **Affinity:** `0xffff`, the 16 P-core threads of the test CPU. Leave it out on other CPUs.
- **Preset switches:** the launcher applies the defaults of `Play-VIctory.cmd`:
  - VICTORY_AMBIENT=0.8
  - VICTORY_AMBIENT_AIR=1.5
  - VICTORY_CARD_AWAKE=1
  - VICTORY_CARD_BUFFERS_MIN_KB=64
  - VICTORY_CARD_REHASH_RUNS=1
  - VICTORY_CARD_STEPS=2
  - VICTORY_INDIRECT_BATCH=2
  - VICTORY_INDIRECT_WINDOW=1
  - VICTORY_JOIN_COPIES=1
  - VICTORY_JOIN_PARTS=8
  - VICTORY_LEVELS_ON_DEMAND=1
  - VICTORY_MAP_THREADS=1
  - VICTORY_RELAY=2
  - VICTORY_RELAY_COPY=1
  - VICTORY_SHOW_AFTER=1
  - VICTORY_TEXTURE_NO_WAIT=1
  - VICTORY_UPLOAD_AHEAD=1
  - VICTORY_WIDE_BACK=1
- **`--diagnose` adds:**
  - VICTORY_LOG=info,victory_gpu::descriptor=error,victory_gpu::pipeline=warn
  - VICTORY_D3D12_DRED=faults
  - VICTORY_CAPTURE_WORLD=1
  - VICTORY_CAPTURE_WORLD_ALSO=144,208
  - VICTORY_CAPTURE_ON_REQUEST=1
  - VICTORY_CAPTURE_TIMELINE=0
  - VICTORY_DUMP_TARGETS=1
  - VICTORY_WINDOW_MAX=1280x720
  - The cache, data and capture folders go under `--state`.
- **`--preset=user-env` adds:**
  - VICTORY_THIN=0: list calls are translated inline, not by 8 helper threads. The preset's 1 is overridden.
  - VICTORY_PIPELINE_WAIT_MS=150: the default is 500.
  - VICTORY_PIPELINE_WORKERS=6: the default is 2/3 of the CPUs.
  - VICTORY_PIPELINE_LOWEST=1: the same as the default.
  - VICTORY_SKIP_WC_BACK=0, VICTORY_SKIP_WC_COMPARE=0 and VICTORY_UP_QUEUE=1 are set as well. Only other forks read them; this tree ignores them.
- **Game settings (`settings.xml`):** use your own; it is not included. The game reads the file
  the same with or without a UTF-8 byte-order mark (tested). The published run used the tester's
  own settings file.
- Game-derived output (shader and pipeline caches, data copies, captures) goes to `--state`,
  `%LOCALAPPDATA%\VIctory\rtx3090` by default. It never goes inside the source tree (`docs/asset-policy.md`).

## Measured on an RTX 3090

All figures are frame times from a diagnostics build at 1280x720. They cover 180 s starting
20 s after the world loads, with the game left on the opening cell-window view.

| Run | median | p90 | draws/frame |
|---|---|---|---|
| Published build (`--preset=user-env`) | 64.3 ms (about 15.6 fps) | 120 ms | 4,549 |
| Same build without the preset | 61–63 ms (about 16 fps) | 112–187 ms | 2,900–4,400 |

The submitting thread is the limit: about 57 ms of each 60 ms frame. The card is 93–98 % busy.

## Known issues

- Bright areas (the sun, strong highlights) can turn black.
- Eyes look wrong at some angles.
- Models stretch in some cutscenes. Five wave64 compute shaders are refused: "no wave32 lowering for this wave64 program".
- Shadow edges are pixelated.
- Some papers on walls show purple (a missing or wrong texture).
- Objects and textures pop in. Some textures differ between runs (a diner table shows a different texture from run to run).
- The phone screen in the diner cutscene is black.
- Colour banding still shows up intermittently.
- Lighting is close but not right.
- The frame rate is about 15–16 fps.
