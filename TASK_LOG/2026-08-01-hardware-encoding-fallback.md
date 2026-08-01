# Hardware encoding with libx264 fallback
Date: 2026-08-01
Status: done
What: Detect H.264 HW encoders at startup (encoder help + 1-frame test) for nvenc/qsv/videotoolbox, fall back to libx264; add `--encoder`; map `--crf`/`--preset` to near-equivalent HW flags; keep yuv420p + faststart for concat `-c copy`.
Files: short-balls/tennis_reels.py, short-balls/README.md, short-balls/TODO.md
