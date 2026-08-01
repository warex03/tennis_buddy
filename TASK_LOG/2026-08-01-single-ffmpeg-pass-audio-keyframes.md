# Single ffmpeg pass for audio + keyframes
Date: 2026-08-01
Status: done
What: Combined audio WAV extract and keyframe sampling into one ffmpeg invocation (`extract_analysis`) with two outputs. Thin wrappers kept; no-audio sources still get keyframes. README pipeline + performance item 12 updated; TODO #4 marked done.
Files: short-balls/tennis_reels.py, short-balls/README.md, short-balls/TODO.md
