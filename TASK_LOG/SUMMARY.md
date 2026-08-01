# Task summary
Updated: 2026-08-01

- Keyframes stay uint8 (no float32 blowup); invalid-range / action-region code promotes only temporary slices/diffs; threshold 28 unchanged; TODO #5 done.
- Cut-list sidecar: after analysis (including `--dry-run`), writes `{basename}_cuts.csv` in `-o` (`source,start,end,duration`); stdlib only; README + TODO #12 updated.
- Parallelized rally encoding in `short-balls/tennis_reels.py` with a CPU-sized `multiprocessing.Pool`; deterministic segment naming/order preserved; README updated.
- Vectorized the `detect_onsets()` rolling median via `sliding_window_view` + `np.median` (every 8 frames); behavior unchanged vs the old list-comp; ~10× faster on synthetic flux; TODO #2 marked done.
- Combined audio + keyframe extract into one ffmpeg pass (`extract_analysis`); wrappers preserved; no-audio still samples keyframes; README pipeline/item 12 and TODO #4 updated.

## Next steps
```
In short-balls/tennis_reels.py, cache deterministic analysis results per input video so re-runs with different --keep / packing options can skip audio extraction, onset detection, keyframe sampling, invalid-range detection, and crop detection. Write a JSON sidecar (e.g. next to the source or under workdir/outdir) containing: onsets, audio duration, invalid ranges, crop box, and enough metadata to invalidate the cache (source path, size, mtime, and/or a content fingerprint). On subsequent runs, load the cache when valid; still recompute segments_for_target from cached onsets+invalid when --keep changes. Add --no-cache / --force-analyze if useful. Document the sidecar in short-balls/README.md. Stdlib + numpy + ffmpeg only. Minimal, robust invalidation.
```
