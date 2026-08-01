# short-balls — delegated improvement prompts

Each section below is a self-contained prompt. Copy one into a new agent session.
Work in `short-balls/tennis_reels.py` (and `short-balls/README.md` when behavior/docs change).
Keep the tool dependency-light: `python3`, `numpy`, `ffmpeg`, `ffprobe` only — no new pip packages unless the prompt says otherwise.

---

## 1. Parallelize segment encoding

```
In short-balls/tennis_reels.py, segment rendering is serial in process() around the loop that calls render_segment for each rally. Parallelize rally encoding with multiprocessing (stdlib only): each rally is independent. Size the worker pool from CPU count (or an optional --jobs N flag). Preserve deterministic output naming/order so pack() and concat still work. Handle worker failures cleanly (fail the run with a clear error). Do not change the encode filter graph or quality settings. Update short-balls/README.md briefly if you add --jobs. Keep the change minimal.
```

---

## 2. Speed up onset median (numpy-only)

```
In short-balls/tennis_reels.py detect_onsets(), replace the slow Python list-comprehension of np.median over a rolling window (the med = np.array([np.median(...) for i in range(0, len(flux), 8)]) block) with a vectorized numpy approach. Stay dependency-free (numpy + stdlib only — no scipy). Preserve the existing behavior as closely as possible: ~1.5s local background, subsampled every 8 frames, then repeated/expanded back to flux length, then MAD/z-score peak picking. Prefer np.lib.stride_tricks.sliding_window_view or an equivalent strided method. Verify with a quick sanity check that onset counts stay in the same ballpark on a short sample if available; otherwise add a tiny unit-style self-check or comment with expected complexity. Keep the change minimal and focused on this hotspot.
```

---

## 3. Cache analysis sidecars

```
In short-balls/tennis_reels.py, cache deterministic analysis results per input video so re-runs with different --keep / packing options can skip audio extraction, onset detection, keyframe sampling, invalid-range detection, and crop detection. Write a JSON sidecar (e.g. next to the source or under workdir/outdir) containing: onsets, audio duration, invalid ranges, crop box, and enough metadata to invalidate the cache (source path, size, mtime, and/or a content fingerprint). On subsequent runs, load the cache when valid; still recompute segments_for_target from cached onsets+invalid when --keep changes. Add --no-cache / --force-analyze if useful. Document the sidecar in short-balls/README.md. Stdlib + numpy + ffmpeg only. Minimal, robust invalidation.
```

---

## 4. Single ffmpeg pass for audio + keyframes

```
In short-balls/tennis_reels.py, extract_audio() and sample_keyframes() each decode/read the source separately. Combine them into one ffmpeg invocation with two outputs (WAV + raw grayscale keyframes) so analysis does one pass over the file. Preserve current formats/params: mono 22.05 kHz WAV; keyframes via -skip_frame nokey, scale 480x270, gray rawvideo. Keep separate helper APIs if that stays clear, but share one underlying extract. Handle the no-audio case without breaking keyframe sampling. Update README pipeline notes if they claim two separate reads. Minimal change; no new dependencies.
```

---

## 5. Reduce keyframe memory (avoid float32 blowup)

```
In short-balls/tennis_reels.py, sample_keyframes() loads all keyframes and immediately casts to float32, which can use ~4x memory on long clips. Keep frames as uint8 (or a compact dtype) for as long as possible. Update find_invalid_ranges() and find_action_region() to work correctly on uint8 (or convert only temporary slices/diffs as needed). Background median and differencing must remain correct; do not silently change thresholds without noting it. Goal: substantially lower peak RAM on hour-long inputs without hurting framing/action detection quality. No new dependencies. Minimal, focused change.
```

---

## 6. Hardware encoding with libx264 fallback

```
In short-balls/tennis_reels.py, detect available hardware H.264 encoders at startup (e.g. h264_nvenc, h264_qsv, maybe VideoToolbox on macOS) and use one when available; fall back to libx264. Map --crf/--preset reasonably onto the HW encoder (or document that HW mode uses a near-equivalent quality flag). Add --encoder auto|libx264|h264_nvenc|h264_qsv (or similar) so users can force a choice. Keep output playable (yuv420p, faststart) and compatible with the existing concat -c copy path. Document in short-balls/README.md. No new Python dependencies. Minimal, reliable detection (probe encoder help or a tiny test encode).
```

---

## 7. Gate rallies on court motion (adjacent-court fix)

```
In short-balls/tennis_reels.py, audio onset detection can mark rallies when ball noise is from an adjacent court while players stand still. After building candidate segments (or inside the segment pipeline), gate each rally using existing keyframe data: require mean frame-difference (or similar motion score) in the action/court region during the segment to exceed the clip's median motion (or another robust baseline). Drop or shrink segments that fail. Reuse sample_keyframes / action region — do not add ML or new dependencies. Log how many segments were rejected and why. Document the failure mode + fix in short-balls/README.md. Keep --keep behavior sensible after gating. Minimal, tunable threshold with a sane default.
```

---

## 8. PTS-accurate keyframe timing for invalid ranges

```
In short-balls/tennis_reels.py, find_invalid_ranges() and the valid_mask for find_action_region() assume uniform keyframe spacing via duration/len(frames). That is wrong for variable GOPs and can trim the wrong times. Obtain real keyframe timestamps (ffprobe show_frames / pkt_pts_time with nokey, or equivalent) aligned 1:1 with sampled frames. Use those timestamps when building invalid ranges and when masking frames for action-region detection. Preserve padding behavior. Handle missing/unreadable PTS gracefully. Update README if it describes the seconds-per-keyframe approximation. No new dependencies. Minimal change focused on timing accuracy.
```

---

## 9. Guard over-budget single rallies in pack()

```
In short-balls/tennis_reels.py, pack() can emit a reel that exceeds --max-duration or --max-size-mb when a single rendered segment alone is over budget. Fix this: either (a) warn loudly and still emit, (b) split the over-long rally at a safe point, or (c) fail with a clear error — pick the most practical approach that fits the "encode once, concat with copy" design (prefer warn + optional mid-rally split only if straightforward). Document behavior in short-balls/README.md. Keep greedy order-preserving packing for the normal case. Minimal change.
```

---

## 10. Fix concat list path quoting

```
In short-balls/tennis_reels.py, concat() writes ffmpeg concat demuxer lines as file '/abs/path' which breaks if the path contains a single quote. Fix path escaping per ffmpeg concat demuxer rules (escape single quotes / special chars, or use a safer approach). Keep -c copy assembly and -safe 0 behavior. Add a brief comment or tiny helper so future edits do not regress. No new dependencies. Minimal fix.
```

---

## 11. Rank rallies before packing

```
In short-balls/tennis_reels.py, reels currently preserve source order when packing. Add optional rally ranking so the strongest clips lead (important for social: first 2 seconds matter). Score each segment using available signals: duration, onset/strike count in range, and/or peak motion from keyframes. Add a flag like --order time|score (default time to preserve current behavior). When score is selected, sort before pack() but still pack with duration/size caps. Log the ranking briefly. Document in short-balls/README.md. No new dependencies. Minimal change.
```

---

## 12. Emit cut-list sidecar (EDL/CSV)

```
In short-balls/tennis_reels.py, after analysis (including --dry-run), write a cut-list sidecar next to outputs or in outdir: CSV and/or a simple EDL listing source file, start, end, duration for each kept rally. Make it easy to import or hand-finish in an editor. Do not require encoding. Document format in short-balls/README.md. Stdlib only for the writer. Minimal, useful columns only.
```

---

## 13. Contact-sheet QA mode

```
In short-balls/tennis_reels.py, add a --contact-sheet (or similar) QA mode that, after rendering a reel (or from sources/segments), tiles a frame every N seconds into one image per reel using ffmpeg. Purpose: verify cuts by eye in one glance. Sensible defaults for tile size and interval; skip gracefully if a reel is empty. Document in short-balls/README.md. No new Python dependencies — shell out to ffmpeg. Minimal feature behind a flag.
```

---

## 14. Add Dockerfile (docs currently lie)

```
short-balls/README.md documents `docker build -t tennis-reels .` but there is no Dockerfile. Add a minimal Dockerfile under short-balls/ that installs ffmpeg and numpy, copies tennis_reels.py, and sets a sensible ENTRYPOINT so the README docker run example works (or update the README commands to match). Keep the image lean. Do not add unnecessary packages. Verify the documented build/run commands are accurate.
```

---

## 15. Validate numpy at startup

```
In short-balls/tennis_reels.py main(), ffmpeg/ffprobe are checked via shutil.which, but a missing numpy only fails at import. Add a clear startup check/error for numpy (or catch ImportError at top with a user-friendly message telling the user how to install it). Keep it consistent with the ffmpeg checks. Minimal change.
```

---

## 16. Motion-gate lens obstructions (bottom-third)

```
In short-balls/tennis_reels.py, find_invalid_ranges() uses a ~15% full-frame (lower-cropped) difference threshold and misses brief lens obstructions when a player walks past the camera. Add a separate check on the bottom third of the frame with a lower threshold to flag short obstruction bursts, then subtract/trim those ranges from segments (prefer trimming out of a rally over dropping the whole rally when possible). Reuse existing keyframe samples. Log detections. Document in README. No new dependencies. Minimal, tunable constants.
```

---

## 17. Multi-angle / multi-framing clustering

```
In short-balls/tennis_reels.py, find_invalid_ranges() assumes one dominant framing and discards the rest. For clips that genuinely switch between two camera positions, this throws away the smaller half. Improve by clustering keyframes into framing groups first, then treating each substantial cluster as its own scene with its own crop (and its own invalid/setup rejection). Fall back to current behavior when there is one clear dominant framing. Keep numpy-only. Document limitations/behavior in short-balls/README.md. This is a larger change — keep the design as simple as possible and avoid over-engineering.
```

---

## 18. Slow-panning crop toward action

```
In short-balls/tennis_reels.py, the vertical layout uses a static action crop wide enough for both near players, so subjects look small. Implement an optional slow-panning crop that eases toward the per-frame (or per-keyframe) action centroid, with a 2–3 second time constant, clamped pan rate, and no seasick motion. Behind a flag (default off). Must still composite onto the blurred backdrop for 9:16 without clipping players badly. Prefer ffmpeg-native approaches if feasible; otherwise precompute a crop keyframe path. Document clearly. No new pip deps. Prefer the simplest approach that works.
```

---

## 19. Optional crossfades between rallies

```
In short-balls/tennis_reels.py, reels are concat'd with stream copy (hard cuts). Add an optional --crossfade flag (e.g. 4–6 frames) using ffmpeg xfade/acrossfade. This cannot use -c copy; re-encode on assemble when the flag is set, and keep the default path as encode-once + copy. Document the quality/time tradeoff in README. No new dependencies. Minimal feature behind the flag.
```

---

## 20. Optional timestamp overlay for review

```
In short-balls/tennis_reels.py, add an optional --timestamp-overlay (or similar) that burn-in the source timestamp via drawtext on each rendered segment — useful for reviewing one's own play, not necessarily for posting. Default off. Keep mute/layout/encode settings working. Document in README. No new dependencies. Minimal change.
```

---

## 21. Warn when crop won't help (non-baseline framings)

```
In short-balls/tennis_reels.py, auto crop assumes a static camera behind the baseline with players roughly symmetric. After find_action_region(), detect when the action region fills most of the frame width (side-on / elevated / already tight) and log a clear warning that re-framing may not help. Do not fail the run. Optional: suggest --layout original. Document the assumption in README. Minimal change.
```
