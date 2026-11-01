#!/usr/bin/env bash
# Makes the 1080p60 clips of docs/linux-benchmark_ja.md in DIR (default ./clips):
#   bbb_1080p60_10s.y4m    Big Buck Bunny (Blender Foundation, CC BY 3.0), 60 fps master,
#                          the 10 s from 1:00 (outdoor, camera and character motion)
#   synth_1080p60_10s.y4m  ffmpeg's testsrc2 over a zooming mandelbrot with temporal noise
# Each is 600 frames, 8-bit 4:2:0, about 1.9 GB. Needs curl, unzip and ffmpeg.
# Usage: scripts/fetch_test_clips.sh [DIR] [SECONDS]
set -euo pipefail
dir="${1:-clips}"
secs="${2:-10}"
mkdir -p "$dir/download"
url=https://download.blender.org/demo/movies/BBB/bbb_sunflower_1080p_60fps_normal.mp4.zip
mp4="$dir/download/bbb_sunflower_1080p_60fps_normal.mp4"
if [ ! -f "$mp4" ]; then
  curl -fL -o "$dir/download/bbb_60.zip" "$url"   # 355 MB
  unzip -o -q "$dir/download/bbb_60.zip" -d "$dir/download"
fi
ffmpeg -hide_banner -loglevel error -y -ss 60 -i "$mp4" -t "$secs" -an -pix_fmt yuv420p \
  -f yuv4mpegpipe "$dir/bbb_1080p60_${secs}s.y4m"
ffmpeg -hide_banner -loglevel error -y \
  -f lavfi -i "testsrc2=size=1920x1080:rate=60:duration=$secs" -f lavfi -i "mandelbrot=size=1920x1080:rate=60" \
  -filter_complex "[1:v]trim=duration=$secs,format=yuv420p[m];[0:v]format=yuv420p[t];[m][t]blend=all_mode=average,noise=alls=6:allf=t,format=yuv420p" \
  -t "$secs" -f yuv4mpegpipe "$dir/synth_1080p60_${secs}s.y4m"
ls -l "$dir"/*.y4m
