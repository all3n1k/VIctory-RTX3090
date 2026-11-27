# The water

Status 2026-11-27. Symptom: the sea renders a flat blue sheet; the console
shows teal-green with light absorption and clearness. Around boats, some
wave-wide configurations instead put black patches on the surface and the hull
cuts a hole in it.

## The four programs

The title names its own shader programs: a container carries its name as a
string, and the log's 16-hex digest is the first 8 bytes of BLAKE3 of the
container bytes. So every refusal names itself; no disassembly needed.

| program | digest | role |
|---|---|---|
| `CS_TransmissionVolumetrics_VolumePortalsOnly_bd25dcd5` | `a10179ab7eda0dc3` | the volume portals that give the water its absorption |
| `CS_TransmissionVolumetricsSubmerged_bbfb2953` | `926c46bab3b86bd6` | the under-surface view |
| `CS_TransmissionVolumetrics_Tiled` | in the allowlist below | reported to put black patches around boats in its wave-wide form |
| `CS_TransmissionVolumetrics_Tiled_LocalLights` | in the allowlist below | the same, with local lights |

## The default is inverted (proven in code)

`crates/victory-shader/src/emit/mod.rs` keeps a `scene_kernel` allowlist of
64-thread compute programs that get the wave-wide form by default. It contains
the two `_Tiled` programs above — and does not contain the two that fix the
water. `wide_on` is `scene_kernel || WIDE_HERE` only while `VICTORY_WAVE_WIDE`
is unset; setting `VICTORY_WAVE_WIDE=0` also switches `VICTORY_WAVE_WIDE_ONLY`
off, so that variable must stay unset.

Consequences:

1. the two programs that damage the water translate, wave-wide, by default;
2. the two that carry absorption are refused (the log's `0x218` lane-mask
   wave64 error) and their draws are dropped — which is why the sea is flat;
3. the arm that revives them ("the water's volume-portals and submerged
   programs", `emit/mod.rs`) never runs for them.

## The staged fix (one warm)

`VICTORY_WAVE_WIDE` unset, and:

```
VICTORY_WAVE_WIDE_ONLY=a10179ab7eda0dc3,926c46bab3b86bd6
```

Both variables are in the shader cache key (`shader_cache.rs`), so every change
costs a warm: ~3.6k pipelines, 5-9 minutes at 6 jobs.

| run | configuration | proves |
|---|---|---|
| A | the two water digests above | whether absorption appears at all |
| B | A, plus the two `_Tiled` entries removed from `scene_kernel` | the reporter's exact configuration |
| C | `VICTORY_WAVE_WIDE=0` | control: nothing wave-wide |

External evidence for B (RTX 5060 Ti, 30 minutes boat to camp): "the water
right (no black patches, the hull cuts no hole in it, the boat floats)". That
report also accepts losing the `_Tiled` dispatches on purpose.

## The trees can ride along

Two tree-culling validation programs fail the same way and reach the same arm:

```
VICTORY_WAVE_WIDE_ONLY=a10179ab7eda0dc3,926c46bab3b86bd6,7c9a6a83826cdfac,21f7ad7863620328
```

`CS_Tree_BatchCull_ValidateInst` / `_ValidateInstInv`. One warm then tells two
stories: whether the water gains its portals, and whether tree pop-in changes.
If the tree pair is still refused with the four-hash list, the widen arm found
no "needs" for them and the ladder stops elsewhere — a different fix.

## What not to do

- Do not allowlist the `_Tiled` programs' wave-wide form to chase the water:
  that is the black-patch configuration.
- Do not set `VICTORY_WAVE_WIDE` at all; unset is the only value that lets
  `VICTORY_WAVE_WIDE_ONLY` work.
- Do not broaden the allowlist wholesale; the broad form is falsified.

## Two measurement traps

- Judge only after the pipeline log says `(0 being made)`. Mid-warm, the water
  reads dark and faces read flat, and the numbers are meaningless.
- `VICTORY_CARD_STEPS=0` costs about 5 fps against `=1` (13.5 against 18.4 on
  one RTX 5070 run) and `=1` is the sweet spot: no vertex stretches, no
  clothes flicker.
