# Reduce keyframe memory (uint8)
Date: 2026-08-01
Status: done
What: Keep loaded keyframes as uint8 instead of casting to float32 (~4× less resident RAM). find_invalid_ranges / find_action_region promote only temporary slices/diffs; threshold 28 unchanged. Sanity-checked against the old float32 path.
Files: short-balls/tennis_reels.py, short-balls/TODO.md
