# Parallelize segment encoding
Date: 2026-08-01
Status: done
What: Rally encoding in process() now uses a multiprocessing.Pool sized to CPU count instead of serial render_segment calls. Segment paths/order unchanged for pack/concat; worker failures exit with a clear error. Encode filter graph and quality settings untouched.
Files: short-balls/tennis_reels.py, short-balls/README.md
