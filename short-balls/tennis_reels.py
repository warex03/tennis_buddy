#!/usr/bin/env python3
"""
tennis_reels.py - turn long, static-camera tennis footage into social-media reels.

What it does
------------
1. Detects ball-strike onsets in the audio track (spectral flux in the 1.2-9 kHz band).
2. Keeps only stretches with a sustained strike rate -> rallies. Pauses longer than
   ~2 s (ball retrieval, walking, standing around) are dropped.
3. Rejects footage where the camera framing does not match the rest of the clip
   (setup / repositioning / empty court) using keyframe background differencing.
4. Auto-detects the region of the frame where play happens.
5. Re-frames to vertical 9:16: the play region sits on a blurred, darkened copy of
   itself so no player is ever cropped out of frame.
6. Packs the rallies into reels bounded by both a max duration and a max file size,
   splitting only on rally boundaries.

Requirements: python3, numpy, ffmpeg, ffprobe.

Example
-------
    python3 tennis_reels.py -i match1.MP4 match2.MP4 -o ./reels --keep 0.55

Author's note: every cut is made on a re-encode of the source, then reels are
assembled with a stream copy, so the footage is encoded exactly once.
"""

import argparse
import json
import math
import multiprocessing
import os
import shutil
import subprocess
import sys
import tempfile
import wave

import numpy as np

# --------------------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------------------

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".m4v", ".webm"}


def log(msg):
    print(f"[reels] {msg}", flush=True)


def expand_inputs(paths):
    """Resolve -i paths: files as-is, directories to video files inside (non-recursive)."""
    files = []
    for p in paths:
        if not os.path.exists(p):
            sys.exit(f"error: no such file or directory: {p}")
        if os.path.isdir(p):
            found = sorted(
                os.path.join(p, name) for name in os.listdir(p)
                if os.path.isfile(os.path.join(p, name))
                and os.path.splitext(name)[1].lower() in VIDEO_EXTS
            )
            if not found:
                sys.exit(f"error: no video files in {p}")
            files.extend(found)
        else:
            files.append(p)
    return files


def run(cmd, **kw):
    """Run a command, raise on failure, never let ffmpeg eat our stdin."""
    return subprocess.run(cmd, check=True, stdin=subprocess.DEVNULL, **kw)


def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,r_frame_rate,codec_name",
         "-show_entries", "format=duration",
         "-of", "json", path],
        check=True, capture_output=True, text=True).stdout
    d = json.loads(out)
    s = d["streams"][0]
    num, den = s["r_frame_rate"].split("/")
    return {
        "width": int(s["width"]),
        "height": int(s["height"]),
        "fps": float(num) / float(den),
        "codec": s["codec_name"],
        "duration": float(d["format"]["duration"]),
    }


def has_audio(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=codec_name", "-of", "csv=p=0", path],
        check=True, capture_output=True, text=True).stdout.strip()
    return bool(out)


# --------------------------------------------------------------------------------------
# 1. audio -> ball-strike onsets
# --------------------------------------------------------------------------------------

def extract_audio(src, wav_path, sr=22050):
    log(f"extracting audio -> {os.path.basename(wav_path)}")
    run(["ffmpeg", "-nostdin", "-v", "error", "-i", src,
         "-vn", "-ac", "1", "-ar", str(sr), "-f", "wav", wav_path, "-y"])


def detect_onsets(wav_path, lo=1200, hi=9000, z_thresh=6.0, refractory=0.18):
    """Spectral-flux onset detection. Returns onset times in seconds.

    A racket hitting a ball is a broadband click: energy appears across a wide
    frequency band within a single analysis frame. Summing only the *positive*
    frame-to-frame change in that band (the 'flux') isolates those attacks and
    largely ignores steady sounds like wind, traffic or conversation.
    """
    w = wave.open(wav_path, "rb")
    sr = w.getframerate()
    x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    w.close()

    N, hop = 1024, 256
    window = np.hanning(N).astype(np.float32)
    nframes = max(0, (len(x) - N) // hop)
    if nframes < 2:
        return np.array([]), len(x) / sr

    freqs = np.fft.rfftfreq(N, 1.0 / sr)
    band = (freqs >= lo) & (freqs <= hi)

    S = np.empty((nframes, int(band.sum())), dtype=np.float32)
    CHUNK = 4096                                    # keeps peak memory modest
    for start in range(0, nframes, CHUNK):
        end = min(nframes, start + CHUNK)
        idx = np.arange(start, end)[:, None] * hop + np.arange(N)[None, :]
        S[start:end] = np.abs(np.fft.rfft(x[idx] * window, axis=1))[:, band]
    S = np.log1p(S * 50.0)                          # compress dynamics

    flux = np.concatenate([[0.0], np.maximum(0.0, np.diff(S, axis=0)).sum(axis=1)])

    dt = hop / sr
    win = int(1.5 / dt)                             # local background over ~1.5 s
    padded = np.pad(flux, (win // 2, win // 2), mode="edge")
    med = np.array([np.median(padded[i:i + win]) for i in range(0, len(flux), 8)])
    med = np.repeat(med, 8)[:len(flux)]
    mad = np.median(np.abs(flux - med)) + 1e-6
    z = (flux - med) / mad                          # robust, loudness-independent

    ref = max(1, int(refractory / dt))
    peaks, i = [], 1
    while i < len(z) - 1:
        if z[i] > z_thresh and flux[i] >= flux[i - 1] and flux[i] >= flux[i + 1]:
            peaks.append(i)
            i += ref
        else:
            i += 1
    return np.array(peaks) * dt, len(x) / sr


# --------------------------------------------------------------------------------------
# 2. video -> keyframe sampling, framing check, action region
# --------------------------------------------------------------------------------------

def sample_keyframes(src, raw_path, w=480, h=270):
    """Decode key frames only (~1 fps) as raw grayscale. Cheap: no full decode."""
    log("sampling keyframes for framing / action analysis")
    run(["ffmpeg", "-nostdin", "-v", "error", "-skip_frame", "nokey", "-i", src,
         "-vsync", "0", "-vf", f"scale={w}:{h},format=gray",
         "-f", "rawvideo", raw_path, "-y"])
    data = np.fromfile(raw_path, dtype=np.uint8)
    n = data.size // (w * h)
    return data[:n * w * h].reshape(n, h, w).astype(np.float32)


def find_invalid_ranges(frames, duration, frac_thresh=0.15, pad=1.5):
    """Time ranges where the frame barely resembles the rest of the video.

    Catches the camera being carried / repositioned, a totally different angle,
    or a lens obstruction. Compares each keyframe against the per-pixel median.
    """
    if len(frames) < 5:
        return []
    bg = np.median(frames, axis=0)
    h = frames.shape[1]
    diff = np.abs(frames[:, int(h * 0.22):, :] - bg[int(h * 0.22):, :])
    frac = (diff > 28).mean(axis=(1, 2))

    spf = duration / len(frames)                    # seconds per keyframe
    bad = np.where(frac > frac_thresh)[0]
    if len(bad) == 0:
        return []
    ranges, s, p = [], bad[0], bad[0]
    for i in bad[1:]:
        if i - p <= 2:
            p = i
        else:
            ranges.append([s * spf, (p + 1) * spf])
            s = p = i
    ranges.append([s * spf, (p + 1) * spf])
    return [[max(0.0, a - pad), min(duration, b + pad)] for a, b in ranges]


def find_action_region(frames, src_w, src_h, valid_mask=None, pad_frac=0.06):
    """Bounding box of where things move, in source pixel coordinates."""
    f = frames if valid_mask is None else frames[valid_mask]
    if len(f) < 3:
        return 0, 0, src_w, src_h
    d = np.abs(np.diff(f, axis=0))
    kh, kw = f.shape[1], f.shape[2]

    def bounds(profile, length, smooth):
        p = np.convolve(profile, np.ones(smooth) / smooth, mode="same")
        base = np.percentile(p, 20)
        cutoff = base + 0.25 * (p.max() - base)
        idx = np.where(p > cutoff)[0]
        if len(idx) == 0:
            return 0, length - 1
        return idx[0], idx[-1]

    # columns: use the vertical band where players actually are
    band = d[:, int(kh * 0.30):int(kh * 0.72), :]
    x0, x1 = bounds(band.mean(axis=(0, 1)), kw, 16)
    y0, y1 = bounds(d.mean(axis=(0, 2)), kh, 6)

    sx, sy = src_w / kw, src_h / kh
    x0, x1 = x0 * sx, (x1 + 1) * sx
    y0, y1 = y0 * sy, (y1 + 1) * sy

    padx = (x1 - x0) * pad_frac
    x0, x1 = max(0, x0 - padx), min(src_w, x1 + padx)
    cw = x1 - x0

    # Height: as much as we can use without wasting the frame on sky/tarmac.
    # Players' apparent size is set by the horizontal scale, so this only
    # controls how much of the vertical canvas the live image fills.
    ch = min(src_h, max(cw * 0.68, (y1 - y0) * 2.2))
    cy = (y0 + y1) / 2 - ch / 2
    cy = min(max(0, cy), src_h - ch)

    to_even = lambda v: int(v) - (int(v) % 2)
    return to_even(x0), to_even(cy), to_even(cw), to_even(ch)


# --------------------------------------------------------------------------------------
# 3. onsets -> rally segments
# --------------------------------------------------------------------------------------

def build_segments(onsets, duration, thresh, invalid=(), window=2.0, merge_gap=1.6,
                   min_len=4.0, pad_in=1.0, pad_out=1.2, grid=0.25):
    """Keep spans where onset density stays above `thresh` hits per +/- `window`."""
    n = int(duration / grid)
    if n < 2:
        return []
    hist = np.zeros(n)
    if len(onsets):
        np.add.at(hist, (np.asarray(onsets) / grid).astype(int).clip(0, n - 1), 1)
    k = int(window / grid)
    density = np.convolve(hist, np.ones(2 * k + 1), mode="same")
    active = density >= thresh

    spans, i = [], 0
    while i < n:
        if active[i]:
            j = i
            while j < n and active[j]:
                j += 1
            spans.append([i * grid, min(j, n - 1) * grid])
            i = j
        else:
            i += 1

    merged = []
    for s, e in spans:
        if merged and s - merged[-1][1] <= merge_gap:
            merged[-1][1] = e
        else:
            merged.append([s, e])

    out = [[max(0.0, s - pad_in), min(duration, e + pad_out)]
           for s, e in merged if e - s >= min_len]

    # re-merge anything the padding glued together
    final = []
    for s, e in out:
        if final and s <= final[-1][1]:
            final[-1][1] = e
        else:
            final.append([s, e])

    return subtract_ranges(final, invalid, min_len)


def subtract_ranges(segments, invalid, min_len):
    if not invalid:
        return segments
    out = []
    for s, e in segments:
        parts = [[s, e]]
        for a, b in invalid:
            nxt = []
            for ps, pe in parts:
                if b <= ps or a >= pe:
                    nxt.append([ps, pe])
                    continue
                if ps < a:
                    nxt.append([ps, min(a, pe)])
                if pe > b:
                    nxt.append([max(b, ps), pe])
            parts = nxt
        out += [p for p in parts if p[1] - p[0] >= min_len]
    return out


def segments_for_target(onsets, duration, invalid, target, **kw):
    """Pick the density threshold that retains ~`target` of the usable footage."""
    usable = duration - sum(min(duration, b) - max(0.0, a) for a, b in invalid)
    usable = max(usable, 1.0)
    best = None
    for thresh in np.arange(2.0, 20.0, 0.25):
        segs = build_segments(onsets, duration, thresh, invalid, **kw)
        frac = sum(e - s for s, e in segs) / usable
        if best is None or abs(frac - target) < abs(best[1] - target):
            best = (thresh, frac, segs)
    return best


# --------------------------------------------------------------------------------------
# 4. rendering
# --------------------------------------------------------------------------------------

def build_filter(crop, out_w, out_h, layout, fade_in, fade_out, dur, mute):
    cx, cy, cw, ch = crop
    crop_f = f"crop={cw}:{ch}:{cx}:{cy}"

    if layout == "vertical":
        bg_w = 120
        bg_h = max(2, int(round(bg_w * out_h / out_w)) // 2 * 2)
        vf = (
            f"[0:v]split=2[bg][fg];"
            f"[bg]{crop_f},scale={bg_w}:{bg_h},gblur=sigma=6,"
            f"scale={out_w}:{out_h}:flags=bicubic,"
            f"eq=brightness=-0.10:saturation=0.75,setsar=1[b];"
            f"[fg]{crop_f},scale={out_w}:-2:flags=lanczos,setsar=1[f];"
            f"[b][f]overlay=(W-w)/2:(H-h)/2,setsar=1,format=yuv420p[v]"
        )
    else:
        vf = f"[0:v]{crop_f},scale={out_w}:-2:flags=lanczos,setsar=1,format=yuv420p[v]"

    if mute:
        return vf, False

    fades = []
    if fade_in:
        fades.append("afade=t=in:st=0:d=0.08")
    if fade_out:
        fades.append(f"afade=t=out:st={max(0.0, dur - 0.08):.3f}:d=0.08")
    vf += f";[0:a]{','.join(fades) if fades else 'anull'}[a]"
    return vf, True


def render_segment(src, start, dur, crop, out_path, args, out_w, out_h, keep_audio):
    filt, mapped_audio = build_filter(
        crop, out_w, out_h, args.layout, True, True, dur, args.mute or not keep_audio)

    cmd = ["ffmpeg", "-nostdin", "-v", "error",
           "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", src,
           "-filter_complex", filt, "-map", "[v]"]
    if mapped_audio:
        cmd += ["-map", "[a]", "-c:a", "aac", "-b:a", args.audio_bitrate]
    else:
        cmd += ["-an"]
    cmd += ["-c:v", "libx264", "-preset", args.preset, "-crf", str(args.crf),
            "-pix_fmt", "yuv420p", "-g", "120",
            "-movflags", "+faststart", out_path, "-y"]
    run(cmd)


def _render_job(job):
    """Worker entry point: encode one rally, return its output byte size."""
    src, start, dur, crop, out_path, args, out_w, out_h, keep_audio = job
    render_segment(src, start, dur, crop, out_path, args, out_w, out_h, keep_audio)
    return os.path.getsize(out_path)


def concat(parts, out_path, workdir, dar):
    listfile = os.path.join(workdir, f"concat_{os.path.basename(out_path)}.txt")
    with open(listfile, "w") as f:
        for p in parts:
            f.write(f"file '{os.path.abspath(p)}'\n")
    run(["ffmpeg", "-nostdin", "-v", "error", "-f", "concat", "-safe", "0",
         "-i", listfile, "-c", "copy", "-aspect", dar,
         "-movflags", "+faststart", out_path, "-y"])


def pack(items, max_dur, max_bytes):
    """Greedy bin-packing of rendered segments into reels. Order is preserved."""
    reels, cur, cur_d, cur_b = [], [], 0.0, 0
    for it in items:
        too_long = cur and cur_d + it["dur"] > max_dur
        too_big = cur and max_bytes and cur_b + it["size"] > max_bytes
        if too_long or too_big:
            reels.append(cur)
            cur, cur_d, cur_b = [], 0.0, 0
        cur.append(it)
        cur_d += it["dur"]
        cur_b += it["size"]
    if cur:
        reels.append(cur)
    return reels


# --------------------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------------------

def process(src, args, workdir, index):
    name = os.path.splitext(os.path.basename(src))[0]
    info = probe(src)
    log(f"{os.path.basename(src)}: {info['width']}x{info['height']} "
        f"{info['fps']:.2f}fps {info['codec']} {info['duration']:.0f}s")

    audio_ok = has_audio(src)
    if not audio_ok:
        log("  !! no audio stream - cannot detect rallies, skipping")
        return []

    wav = os.path.join(workdir, f"{name}.wav")
    extract_audio(src, wav)
    onsets, adur = detect_onsets(wav)
    log(f"  {len(onsets)} ball-strike onsets ({len(onsets) / max(adur, 1) * 60:.0f}/min)")

    raw = os.path.join(workdir, f"{name}.raw")
    frames = sample_keyframes(src, raw)

    invalid = [] if args.no_framing_check else find_invalid_ranges(frames, info["duration"])
    if invalid:
        lost = sum(b - a for a, b in invalid)
        log(f"  dropping {lost:.0f}s of off-framing / setup footage: "
            + ", ".join(f"{a:.0f}-{b:.0f}s" for a, b in invalid[:6]))

    if args.crop:
        crop = args.crop
    else:
        spf = info["duration"] / max(len(frames), 1)
        mask = np.ones(len(frames), dtype=bool)
        for a, b in invalid:
            mask[int(a / spf):int(math.ceil(b / spf))] = False
        crop = find_action_region(frames, info["width"], info["height"],
                                  mask if mask.sum() > 5 else None)
    log(f"  action region: {crop[2]}x{crop[3]} at +{crop[0]}+{crop[1]}")

    thresh, frac, segs = segments_for_target(onsets, info["duration"], invalid, args.keep)
    total = sum(e - s for s, e in segs)
    log(f"  {len(segs)} rallies, {total:.0f}s kept ({frac * 100:.0f}% of usable footage), "
        f"density threshold {thresh:.2f}")

    if args.dry_run:
        for s, e in segs:
            log(f"    {s:7.1f} - {e:7.1f}  ({e - s:.1f}s)")
        return []

    if args.layout == "vertical":
        out_w, out_h = args.width, int(round(args.width * 16 / 9)) // 2 * 2
        dar = "9:16"
    else:
        out_w = args.width
        out_h = int(round(args.width * crop[3] / crop[2])) // 2 * 2
        g = math.gcd(out_w, out_h)
        dar = f"{out_w // g}:{out_h // g}"

    jobs = [
        (src, s, e - s, crop, os.path.join(workdir, f"{name}_seg{i:03d}.mp4"),
         args, out_w, out_h, audio_ok)
        for i, (s, e) in enumerate(segs)
    ]
    workers = max(1, min(len(jobs), os.cpu_count() or 1))
    log(f"  rendering {len(jobs)} rallies with {workers} workers")
    try:
        with multiprocessing.Pool(workers) as pool:
            sizes = pool.map(_render_job, jobs)
    except Exception as exc:
        sys.exit(f"error: rally encode failed: {exc}")

    rendered = [
        {"path": job[4], "dur": job[2], "size": size}
        for job, size in zip(jobs, sizes)
    ]
    return [{"name": name, "index": index, "dar": dar, "items": rendered}]


def main():
    p = argparse.ArgumentParser(
        description="Cut static-camera tennis footage into vertical highlight reels.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("-i", "--input", nargs="+", required=True,
                   help="source video file(s) and/or folder(s) of videos")
    p.add_argument("-o", "--outdir", default="./reels", help="where finished reels go")
    p.add_argument("--keep", type=float, default=0.55,
                   help="target share of usable footage to retain (0-1); lower = tighter")
    p.add_argument("--max-duration", type=float, default=240.0, help="max reel length, seconds")
    p.add_argument("--max-size-mb", type=float, default=100.0,
                   help="max reel size in MB (0 disables)")
    p.add_argument("--layout", choices=["vertical", "original"], default="vertical",
                   help="'vertical' = 9:16 on a blurred backdrop; 'original' = keep the crop's aspect")
    p.add_argument("--width", type=int, default=1080, help="output width in pixels")
    p.add_argument("--crf", type=int, default=17, help="x264 quality; lower = better, 17 is near-transparent")
    p.add_argument("--preset", default="veryfast", help="x264 speed preset")
    p.add_argument("--audio-bitrate", default="192k")
    p.add_argument("--mute", action="store_true", help="drop audio (add music later in-app)")
    p.add_argument("--crop", type=str, default=None,
                   help="override auto-detected action region, as WxH+X+Y")
    p.add_argument("--no-framing-check", action="store_true",
                   help="keep footage even if the camera framing changes")
    p.add_argument("--dry-run", action="store_true", help="analyse and print the cut list, render nothing")
    p.add_argument("--workdir", default=None, help="scratch dir (default: a temp dir, removed on exit)")
    args = p.parse_args()

    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            sys.exit(f"error: {tool} not found on PATH")

    if args.crop:
        try:
            wh, x, y = args.crop.replace("+", " ").split()
            cw, ch = wh.lower().split("x")
            args.crop = (int(x), int(y), int(cw), int(ch))
        except ValueError:
            sys.exit("error: --crop must look like 1320x900+240+110")

    os.makedirs(args.outdir, exist_ok=True)
    tmp = args.workdir or tempfile.mkdtemp(prefix="tennis_reels_")
    os.makedirs(tmp, exist_ok=True)
    log(f"workdir: {tmp}")

    try:
        sources = expand_inputs(args.input)
        log(f"inputs: {len(sources)} video(s)")
        groups = []
        for n, src in enumerate(sources, 1):
            groups += process(src, args, tmp, n)

        if args.dry_run:
            return

        max_bytes = int(args.max_size_mb * 1000 * 1000) if args.max_size_mb else 0
        written = []
        for g in groups:
            reels = pack(g["items"], args.max_duration, max_bytes)
            for i, reel in enumerate(reels, 1):
                suffix = f"_{i}" if len(reels) > 1 else ""
                out = os.path.join(args.outdir, f"{g['name']}_reel{suffix}.mp4")
                concat([r["path"] for r in reel], out, tmp, g["dar"])
                dur = sum(r["dur"] for r in reel)
                size = os.path.getsize(out) / 1e6
                log(f"wrote {out}  {int(dur // 60)}:{int(dur % 60):02d}  {size:.0f} MB")
                written.append(out)

        log(f"done - {len(written)} reel(s) in {args.outdir}")
    finally:
        if not args.workdir:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
