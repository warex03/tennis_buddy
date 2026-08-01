# Short balls (reels creator)

Turn long, static-camera tennis footage into vertical highlight reels ready for
Instagram Reels, TikTok or YouTube Shorts. Dead time — ball retrieval, walking
between points, standing around — is detected and dropped automatically.

Python, not bash — the rally detection is numeric (FFTs, rolling medians,
thresholds), which shell can't do without dragging in extra tools. It shells out
to ffmpeg for everything media-related.

---

## Features

- **Automatic rally detection from audio.** Finds ball strikes by spectral-flux
  onset detection, then keeps only stretches where the strike rate stays high.
  No manual scrubbing, no fixed loudness threshold to tune per court.
- **Automatic dead-time removal.** Pauses longer than roughly 2 seconds fall out
  of the cut on their own.
- **Bad-framing rejection.** Footage where the camera was still being positioned,
  pointed elsewhere, or blocked is detected and excluded before cutting.
- **Automatic action-region detection.** Works out where on the court play
  actually happens, so the crop is derived from the footage rather than guessed.
- **9:16 re-framing without clipping players.** The play area is composited over
  a blurred, darkened copy of itself, so nobody gets cropped out of frame.
- **Adaptive tightness.** `--keep` sets how much of the usable footage to retain;
  the density threshold is solved for automatically per clip.
- **Size- and duration-bounded reels.** Reels are bin-packed against both a max
  length and a max file size, splitting only on rally boundaries.
- **Encoded exactly once.** Rallies are encoded individually and reels are
  assembled with a stream copy, so later trims and splits cost nothing in quality.
- **Parallel rally encoding.** Independent rallies encode concurrently via a
  `multiprocessing` pool (`--jobs`; auto = CPU count).
- **libx264 encode.** Software H.264 for broad player compatibility.
- **Original quality preserved.** 60 fps retained, CRF 17, lanczos downscale,
  square pixels, original court audio (or `--mute` to add music in-app).
- **Dry-run mode.** Print the cut list in seconds before committing CPU to encoding.
- **Cut-list sidecar.** After analysis (including `--dry-run`), writes
  `{source}_cuts.csv` in `-o/tennis_reels_<filename>/` with each kept rally —
  no encoding required.

---

## Requirements

`ffmpeg`, `ffprobe`, `python3`, `numpy`. Nothing else — no pip install step.

## Usage

### From the repo root (Makefile)

Put source videos in `short-balls/inputs`, then from the repo root:

```bash
make build          # first time
make run            # encode → short-balls/reels
make dry-run        # analyse + cut-list CSV only
```

Extra flags via `ARGS`; a specific file/folder via `INPUT` (path inside the container):

```bash
make dry-run INPUT=inputs/1.MP4
make run INPUT=inputs/2026-08-01   # nested folder (see below)
make run ARGS='--keep 0.4 --mute'
make help           # list targets
```

### From the repo root (Docker Compose)

Put source videos in `short-balls/inputs`, then from the repo root:

```bash
docker compose run --rm tennis-reels -i inputs
```

`-i` accepts files and/or folders; a folder expands to all videos **directly** inside it (`.mp4`, `.mov`, `.mkv`, `.avi`, `.m4v`, `.webm`) — **not recursive**. If your clips live in a subfolder (e.g. `short-balls/inputs/2026-08-01/*.MP4`), pass that path instead:

```bash
docker compose run --rm tennis-reels -i inputs/2026-08-01
# or: make run INPUT=inputs/2026-08-01
```

Otherwise `-i inputs` sees only the subfolder name and exits with `error: no video files in inputs`. Host mounts: `short-balls/inputs` → `/work/inputs`, `short-balls/reels` → `/work/reels` (default `-o`). For each source video, outputs land in `-o/tennis_reels_<filename>/` (intermediates, cut list, and finished reels) — nothing is written under `/tmp`.

On startup the entrypoint `chown`s those bind mounts to your host UID/GID (from `UID`/`GID`, defaulting to `1000`), then drops privileges before encoding. So if Docker recreated `inputs`/`reels` as root after you deleted them, the next `make run` / `docker compose run` makes them writable again. Prefer `make` (exports `UID`/`GID`); for raw Compose, export them yourself if your user is not `1000`.

See the cut list without spending time on encoding:

```bash
make dry-run INPUT=inputs/1.MP4
```

### Cut-list CSV

After analysis (including `--dry-run`), each source gets
`-o/tennis_reels_<basename>/{basename}_cuts.csv`. Columns (seconds, 3 decimal
places):

| Column | Meaning |
| --- | --- |
| `source` | Absolute path to the input video |
| `start` | Rally start time |
| `end` | Rally end time |
| `duration` | `end - start` |

Import into a spreadsheet or map the ranges into your editor for hand-finishing.
No encoding is required for this file to be written.

---

## What the pipeline does

**1. Probe.** `ffprobe` for dimensions, fps, codec, duration.

**2. Extract audio + keyframes in one pass.** A single ffmpeg read writes mono
22.05 kHz WAV and keyframe-only (`-skip_frame nokey`, ~1 fps) 480x270 grayscale
rawvideo. No-audio sources still get keyframes (WAV is skipped).

**3. Find ball strikes in the audio.** Spectral-flux onset detection on the WAV:
STFT (1024-sample window, 256 hop), keep the 1.2–9 kHz band, and sum only the
*positive* frame-to-frame change in magnitude. A racket hitting a ball is a
broadband click — energy jumps across the whole band in one frame. Steady sounds
like wind and conversation don't produce that jump. Peaks are picked against a
rolling local median scaled by MAD, so the threshold adapts to ambient level
instead of being an absolute loudness cutoff.

**4. Turn strikes into rallies.** Count onsets in a ±2s window on a 0.25s grid.
Where that density stays above a threshold, it's a rally. Merge spans separated
by under 1.6s, drop anything shorter than 4s, pad 1.0s before and 1.2s after so
you see the wind-up and the finish. Pauses longer than about 2s fall out on their
own — this is what removes ball retrieval and walking. The threshold isn't
hardcoded; the script sweeps it and picks the value hitting your `--keep` target.

**5. Reject bad framing.** From the keyframes already extracted: take the
per-pixel median as the background, then flag frames where more than 15% of
pixels differ from it. That's what caught the first 52 seconds of 1.MP4, where
the camera was still being positioned on an empty court. Audio alone had happily
marked it as play, since there was ball noise nearby.

**6. Locate the action.** From those same keyframes, difference consecutive
frames and build column and row motion profiles. The columns show two clear peaks
— your near players — and the bounding box across them defines the crop.
Auto-detection lands on 1266x862+276+110 for your footage; I'd hand-tuned
1320x900+240+110.

**7. Re-frame to 9:16.** The action is far too wide for a straight vertical crop;
anything narrow enough for 9:16 clips a near player. So the crop is scaled to
1080 wide and laid over a blurred, darkened copy of itself. `setsar=1` appears on
every branch — this is the bug that made your first render look stretched. The
scale filter compensates for aspect changes by adjusting the sample aspect ratio,
and the heavily downscaled background branch carried SAR 352:135 into the overlay
output.

**8. Encode once, assemble with copies.** Each rally is encoded separately
(H.264 via `libx264`, quality ≈ CRF 17, lanczos downscale, 60fps preserved,
80ms audio fades to avoid clicks at the joins), in parallel across a process
pool (`--jobs`; auto uses CPU count). Segments stay `yuv420p` + `faststart`
so the later `-c copy` concat stays playable. Segment names and order stay fixed
so packing is unchanged. Reels are then bin-packed by both duration and *actual
measured file size*, and joined with `-c copy`. Splitting or trimming a reel
later — like your 45s cut and the 100MB split — just re-concatenates different
subsets, no re-encoding, no generation loss.

Useful knobs: `--keep 0.4` for a tighter cut, `--dry-run` to see the cut list
before committing CPU, `--crop` to override the region, `--mute` if you'll add
music in-app.

---

## Options

| Flag | Default | What it does |
| --- | --- | --- |
| `-i`, `--input` | — | Source video file(s) and/or folder(s) of videos |
| `-o`, `--outdir` | `./reels` | Parent of per-video `tennis_reels_<filename>/` folders |
| `--keep` | `0.55` | Target share of usable footage to retain; lower is tighter |
| `--max-duration` | `240` | Max reel length in seconds |
| `--max-size-mb` | `100` | Max reel size; `0` disables the size cap |
| `--layout` | `vertical` | `vertical` = 9:16 on a blurred backdrop, `original` = keep the crop's aspect |
| `--width` | `1080` | Output width in pixels |
| `--jobs` | `0` (auto) | Parallel rally encodes; auto = CPU count |
| `--crf` | `17` | libx264 quality; lower is better |
| `--preset` | `veryfast` | libx264 speed preset |
| `--audio-bitrate` | `192k` | AAC bitrate |
| `--mute` | off | Drop audio entirely |
| `--crop` | auto | Override the action region, as `WxH+X+Y` |
| `--no-framing-check` | off | Keep footage even when the camera framing changes |
| `--dry-run` | off | Analyse, write cut-list CSV, render nothing |

---

## Recommendations for improving the script

Roughly in order of value for effort.

### Correctness and robustness

1. **Validate rallies visually, not just acoustically.** The audio detector has
   one known failure mode: it fires on ball sounds from *adjacent courts*. The
   framing check catches the empty-court case, but not "someone else is rallying
   nearby while your group stands around." A cheap fix is to require player
   motion in the court region during a candidate rally — you already decode
   keyframes, so gate each segment on the mean frame-difference exceeding the
   clip's median.
2. **Detect lens obstructions.** When a player walks past the camera they fill
   the frame for a second or two. The current 15% threshold only catches
   full-frame changes. A separate, lower threshold restricted to the bottom third
   of the frame would flag these so they can be trimmed out of a segment rather
   than dropping the whole rally.
3. **Handle multi-angle footage.** `find_invalid_ranges` assumes one dominant
   framing and treats everything else as invalid. If a clip is genuinely split
   between two camera positions, it will throw away the smaller half. Cluster the
   keyframes first, then process each cluster as its own scene with its own crop.
4. **Guard the segment-longer-than-reel case.** A single rally exceeding
   `--max-duration` or `--max-size-mb` currently becomes an over-budget reel of
   its own. Either split it mid-rally at a keyframe or warn loudly.

### Output quality

5. **Track the action with a slow-panning crop.** A crop that eases toward the
   ball would let you zoom in significantly — players are currently at 0.82x
   because the crop must be wide enough for both near players simultaneously.
   Smooth the per-frame action centroid heavily (a 2–3 second time constant) to
   avoid seasick panning, and clamp the pan rate.
6. **Add short crossfades between rallies.** Hard cuts are normal for highlight
   reels, but a 4–6 frame dissolve reads as more deliberate. This needs the
   `xfade` filter and cannot be done with a stream-copy concat, so it belongs
   behind a flag.
7. **Rank rallies instead of taking them in order.** Score each by length, strike
   count and peak movement, then lead with the best one. Reels live or die on the
   first two seconds.
8. **Optional score/timestamp overlay.** `drawtext` with the source timestamp is
   useful for reviewing your own play even if you'd never post it.

### Performance

9. ~~**Parallelise segment rendering.**~~ Done — `multiprocessing.Pool` sized to
   CPU count encodes rallies concurrently.
10. **Cache the analysis.** Onsets, invalid ranges and the crop box are
    deterministic per input. Write them to a JSON sidecar so re-running with a
    different `--keep` skips straight to encoding.
11. ~~**Reuse one decode pass.**~~ Done — `extract_analysis()` writes mono WAV and
    grayscale keyframe rawvideo from one ffmpeg invocation with two outputs.

### Usability

12. ~~**Emit a cut-list sidecar**~~ Done — `{basename}_cuts.csv` in `-o` after
    analysis (including `--dry-run`): `source,start,end,duration`.
13. **Add a contact-sheet QA mode** that tiles a frame every N seconds from each
    finished reel. This is how the cuts were verified by eye during development
    and it catches a bad detection in one glance.
14. **Support other framings.** The current assumptions — static camera, behind
    the baseline, players roughly symmetric about centre — hold for your setup but
    not for a side-on or elevated camera. At minimum, detect and warn when the
    action region fills most of the frame width, which is the signal that the
    crop is not going to help.
