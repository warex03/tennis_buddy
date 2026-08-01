# Task summary
Updated: 2026-08-01

- Hardware H.264 encoding: startup probe (encoder help + 1-frame test) for `h264_nvenc` / `h264_qsv` / `h264_videotoolbox`, fall back to `libx264`; `--encoder` to force; `--crf`/`--preset` mapped per encoder; yuv420p + faststart kept; README + TODO #6 done.
- Keyframes stay uint8 (no float32 blowup); invalid-range / action-region code promotes only temporary slices/diffs; threshold 28 unchanged; TODO #5 done.
- Cut-list sidecar: after analysis (including `--dry-run`), writes `{basename}_cuts.csv` in `-o` (`source,start,end,duration`); stdlib only; README + TODO #12 updated.
- Parallelized rally encoding in `short-balls/tennis_reels.py` with a CPU-sized `multiprocessing.Pool`; deterministic segment naming/order preserved; README updated.
- Vectorized the `detect_onsets()` rolling median via `sliding_window_view` + `np.median` (every 8 frames); behavior unchanged vs the old list-comp; ~10× faster on synthetic flux; TODO #2 marked done.
- Combined audio + keyframe extract into one ffmpeg pass (`extract_analysis`); wrappers preserved; no-audio still samples keyframes; README pipeline/item 12 and TODO #4 updated.

## Next steps
```
In short-balls/tennis_reels.py, audio onset detection can mark rallies when ball noise is from an adjacent court while players stand still. After building candidate segments (or inside the segment pipeline), gate each rally using existing keyframe data: require mean frame-difference (or similar motion score) in the action/court region during the segment to exceed the clip's median motion (or another robust baseline). Drop or shrink segments that fail. Reuse sample_keyframes / action region — do not add ML or new dependencies. Log how many segments were rejected and why. Document the failure mode + fix in short-balls/README.md. Keep --keep behavior sensible after gating. Minimal, tunable threshold with a sane default.
```
