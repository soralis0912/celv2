#!/usr/bin/env python3
"""Timed speed run: codes for a fixed wall time, stops celv2enc, and reports the frames done.

Usage:
  scripts/bench_time.py -i clip.y4m --minutes 1 [--out-dir DIR] [--avmdec PATH] [-- celv2enc options]

On a slow machine a whole clip takes hours; this measures the speed in a fixed time instead.
celv2enc runs with --progress; each "progress frame=N" line is timed. At the limit it gets SIGTERM
(SIGKILL 10 s later), the IVF is cut after its last complete frame, and the run prints:

  frames written in the time; fps = frames / the whole time (a lower bound: the mini-GOP being
  coded when the time runs out is lost) and fps_last = frames / the time of the last write (an
  upper bound: frames come out a mini-GOP at a time); with --avmdec the luma PSNR, and the bitrate
  of the frames written.

The two bounds close in as the run gets longer: 1 minute tells the order, 10 minutes the speed. Files in DIR: out.ivf (cut), progress.csv (frame, seconds),
stderr.txt, summary.json. A clip shorter than the time just ends early.
"""
import argparse
import json
import os
import re
import signal
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def y4m_info(path):
    with open(path, 'rb') as f:
        line = f.readline().decode('ascii', 'replace')
    w = int(re.search(r' W(\d+)', line).group(1))
    h = int(re.search(r' H(\d+)', line).group(1))
    fn, fd = map(int, re.search(r' F(\d+):(\d+)', line).groups())
    c = re.search(r' C(\S+)', line)
    return w, h, fn, fd, c.group(1) if c else '420jpeg'


def cut_ivf(path):
    """Drops a partly written last frame; fixes the header's frame count. Returns (frames, bytes)."""
    data = bytearray(Path(path).read_bytes())
    if len(data) < 32 or data[:4] != b'DKIF':
        return 0, 0
    hdr = struct.unpack_from('<H', data, 6)[0]
    pos, n, payload = hdr, 0, 0
    while pos + 12 <= len(data):
        size = struct.unpack_from('<I', data, pos)[0]
        if pos + 12 + size > len(data):
            break
        pos += 12 + size
        payload += size
        n += 1
    del data[pos:]
    struct.pack_into('<I', data, 24, n)
    Path(path).write_bytes(data)
    return n, payload


def psnr_y(avmdec, ivf, src, frames, w, h, rate, chroma, work):
    """Mean luma PSNR of the decoded frames against the source, at the source's depth."""
    yuv = work / 'dec.yuv'
    ten = chroma.startswith('420p10')
    pix = 'yuv420p10le' if ten else 'yuv420p'
    subprocess.run([avmdec, '--rawvideo', f'--output-bit-depth={10 if ten else 8}', '-o', str(yuv), str(ivf)],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # rawvideo needs the source's frame rate, or the psnr filter pairs the wrong frames.
    r = subprocess.run(['ffmpeg', '-hide_banner', '-f', 'rawvideo', '-pix_fmt', pix, '-s', f'{w}x{h}',
                        '-framerate', rate, '-i', str(yuv), '-i', str(src), '-frames:v', str(frames),
                        '-lavfi', '[0:v][1:v]psnr', '-f', 'null', '-'],
                       capture_output=True, text=True)
    yuv.unlink()
    m = re.search(r'PSNR y:([0-9.]+)', r.stderr)
    return float(m.group(1)) if m else None


def main():
    argv = sys.argv[1:]
    extra = []
    if '--' in argv:
        i = argv.index('--')
        argv, extra = argv[:i], argv[i + 1:]
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('-i', '--input', required=True)
    t = ap.add_mutually_exclusive_group(required=True)
    t.add_argument('--minutes', type=float)
    t.add_argument('--seconds', type=float)
    ap.add_argument('--out-dir', default=None)
    ap.add_argument('--celv2enc', default=str(ROOT / 'build' / 'celv2enc'))
    ap.add_argument('--avmdec', default=os.environ.get('AVMDEC'), help='for PSNR; default $AVMDEC')
    a = ap.parse_args(argv)
    limit = a.seconds if a.seconds is not None else a.minutes * 60
    src = Path(a.input).resolve()
    w, h, fn, fd, chroma = y4m_info(src)
    out = Path(a.out_dir or f'bench_{src.stem}_{int(limit)}s').resolve()
    out.mkdir(parents=True, exist_ok=True)
    ivf = out / 'out.ivf'
    cmd = [a.celv2enc, '-i', str(src), '-o', str(ivf), '--progress'] + extra
    print('run:', ' '.join(cmd), f'(limit {limit:.0f} s)', file=sys.stderr)

    marks = []  # (frame, seconds)
    errlog = open(out / 'stderr.txt', 'w')
    t0 = time.monotonic()
    p = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True, bufsize=1)

    def reader():
        for line in p.stderr:
            now = time.monotonic() - t0
            errlog.write(line)
            m = re.match(r'progress frame=(\d+)', line)
            if m:
                marks.append((int(m.group(1)), now))
                print(f'\r{now:7.1f} s  frame {m.group(1)}', end='', file=sys.stderr, flush=True)
    th = threading.Thread(target=reader, daemon=True)
    th.start()
    stopped = False
    try:
        p.wait(timeout=limit)
    except subprocess.TimeoutExpired:
        stopped = True
        p.send_signal(signal.SIGTERM)
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait()
    elapsed = min(time.monotonic() - t0, limit) if stopped else time.monotonic() - t0
    th.join(timeout=5)
    errlog.close()
    print(file=sys.stderr)
    if not stopped and p.returncode != 0:
        sys.exit(f'celv2enc failed (exit {p.returncode}), see {out / "stderr.txt"}')

    with open(out / 'progress.csv', 'w') as f:
        f.write('frame,seconds\n')
        for n, s in marks:
            f.write(f'{n},{s:.3f}\n')
    frames, payload = cut_ivf(ivf)
    # Count only what the cut file holds (a frame announced just before the kill may be cut).
    in_time = [s for n, s in marks if n <= frames]
    fps = frames / elapsed if elapsed > 0 else 0.0
    fps_last = frames / in_time[-1] if in_time and in_time[-1] > 0 else None
    rate = f'{fn}/{fd}'
    res = {
        'input': str(src), 'size': f'{w}x{h}', 'rate': rate, 'options': extra,
        'limit_s': limit, 'elapsed_s': round(elapsed, 2), 'stopped_at_limit': stopped,
        'frames_written': frames,
        'first_frame_s': round(in_time[0], 2) if in_time else None,
        'fps': round(fps, 4), 'fps_last': round(fps_last, 4) if fps_last else None,
        'frames_per_minute': round(fps * 60, 2),
        'kbps': round(payload * 8 / (frames * fd / fn) / 1000, 1) if frames else None,
    }
    if a.avmdec and frames:
        res['psnr_y'] = psnr_y(a.avmdec, ivf, src, frames, w, h, rate, chroma, out)
    (out / 'summary.json').write_text(json.dumps(res, indent=2) + '\n')
    for k, v in res.items():
        print(f'{k:18} {v}')
    if not frames:
        print('no frame written in the time: give it longer (the first frame waits for its mini-GOP)',
              file=sys.stderr)


if __name__ == '__main__':
    main()
