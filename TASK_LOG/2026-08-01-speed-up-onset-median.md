# Speed up onset median (numpy-only)
Date: 2026-08-01
Status: done
What: Replaced the Python list-comprehension rolling median in detect_onsets() with np.lib.stride_tricks.sliding_window_view + np.median (subsample every 8 frames, same expand/MAD/z-score path). Exact match vs old medians on synthetic flux; ~10× faster at n=50k.
Files: short-balls/tennis_reels.py, short-balls/TODO.md
