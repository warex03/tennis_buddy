# Task summary
Updated: 2026-08-01

- Parallelized rally encoding in `short-balls/tennis_reels.py` with a CPU-sized `multiprocessing.Pool`; deterministic segment naming/order preserved; README updated.

## Next steps
```
In short-balls/tennis_reels.py detect_onsets(), replace the slow Python list-comprehension of np.median over a rolling window (the med = np.array([np.median(...) for i in range(0, len(flux), 8)]) block) with a vectorized numpy approach. Stay dependency-free (numpy + stdlib only — no scipy). Preserve the existing behavior as closely as possible: ~1.5s local background, subsampled every 8 frames, then repeated/expanded back to flux length, then MAD/z-score peak picking. Prefer np.lib.stride_tricks.sliding_window_view or an equivalent strided method. Verify with a quick sanity check that onset counts stay in the same ballpark on a short sample if available; otherwise add a tiny unit-style self-check or comment with expected complexity. Keep the change minimal and focused on this hotspot.
```
