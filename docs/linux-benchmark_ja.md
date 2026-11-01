# Linux での性能検証手順

celv2enc を Linux マシン上でビルドし、1080p60 の動画で速度（fps）と画質（PSNR）を測る手順。
GPU が無いマシンでは CPU エンジンで符号化するので非常に遅く、クリップを最後まで符号化すると
何時間もかかる。そのため **一定時間（1 分 / 10 分）だけ符号化して止め、書き出せたフレーム数から
fps を出す** 方式（`scripts/bench_time.py`）で測る。

## 0. 前提

- x86-64 Linux、AVX2 のある CPU（`grep -c avx2 /proc/cpuinfo` が 0 でないこと）
- 確認した環境: Ubuntu 24.04、GCC 13.3（celv2）、Clang 18（AVM）、CMake 3.28、
  AMD EPYC 7642 ×2（192 スレッド）、GPU なし
- ディスク: AVM のソースとビルドで約 2 GB、テスト動画 1 本（1080p60 10 秒の y4m）で約 1.9 GB
- CUDA と Vulkan は任意。無ければビルド時に自動で外れ、判定は CPU で行う（出力のバイト列は
  どのエンジンでも同じ）

## 1. 依存パッケージ

```sh
sudo apt install build-essential clang cmake ninja-build nasm ffmpeg git curl unzip python3
```

- `nasm`: AVM のアセンブリに必要
- `ffmpeg` / `ffprobe`: テスト動画の作成と PSNR の計算に使う
- 任意: CUDA toolkit 13.x（`nvcc` が PATH にあれば CUDA エンジンが入る）、Vulkan SDK または
  `libvulkan-dev` と `slangc`（Vulkan エンジン）

## 2. AVM v1.0.0 の取得とビルド

celv2 は AVM v1.0.0（コミット `966a7d7cd6fcf60360caf5dc413b2aeeb65e144d`）をライブラリとして
リンクする。**`v1.0.0` タグは GitHub 側にある**（GitLab のミラーには `research-v*` のタグしか無く、
このコミットも取れない）。

```sh
git clone --depth 1 --branch v1.0.0 https://github.com/AOMediaCodec/avm.git ~/avm
git -C ~/avm rev-parse HEAD     # 966a7d7cd6fcf60360caf5dc413b2aeeb65e144d であること
export AVM_ROOT=~/avm           # 省略時は ~/avm
cd celv2
scripts/build_avm_lib.sh        # ~/avm/_build_lib に libavm.a、avmenc、avmdec ができる
```

AVM の CMake は TFLite などの依存をネットから取ってくるので、初回はネット接続が要る。
192 スレッドのマシンでビルドは数分。

## 3. celv2 のビルドとテスト

```sh
scripts/build.sh                # build/celv2enc ができる
```

configure の出力に次が出る。GPU なしのマシンでは両方 off で正常。

```
-- CUDA engine: OFF
-- Vulkan: off (no Vulkan headers or slangc)
```

CUDA を入れてあっても外したいときは `CELV2_CMAKE_ARGS=-DCELV2_CUDA=OFF scripts/build.sh`。

テスト:

```sh
CTEST_JOBS=16 scripts/test.sh -E test_cli    # 1 分弱
scripts/test.sh -R test_cli                  # CPU だけだと 20 分以上かかる。時間のあるときに
```

- CUDA なしのビルドでは CUDA 専用のテスト（`test_gpu_intra`、`test_keyframe_gpu`、`test_gpu_me`、
  `test_ippp`、`test_vk_kernels`）はビルドされない
- `test_cli` は celv2enc を何十回も実行するので CPU エンジンでは時間がかかる（タイムアウトは
  1200 秒）。性能検証が目的なら `-E test_cli` で十分

動作確認:

```sh
build/celv2enc --list-devices    # GPU なしなら "cpu	CPU" だけ
```

## 4. テスト動画（1080p60）

```sh
scripts/fetch_test_clips.sh ~/clips      # 10 秒ずつ。2 番目の引数で秒数を変えられる
```

できるもの（どちらも 1920x1080、60 fps、8 bit 4:2:0、600 フレーム、約 1.9 GB の y4m）:

| ファイル | 内容 |
|---|---|
| `bbb_1080p60_10s.y4m` | Big Buck Bunny（Blender Foundation、CC BY 3.0）の 60 fps 版マスター（355 MB の zip）から 1:00〜1:10 を切り出したもの。屋外、カメラと動物の動きあり |
| `synth_1080p60_10s.y4m` | ffmpeg で生成。`testsrc2` とズームする `mandelbrot` を重ね、時間方向のノイズを加えたもの。ネット不要 |

Big Buck Bunny の出典表記: (c) copyright 2008, Blender Foundation / www.bigbuckbunny.org

手元の別の動画を使うときは y4m（4:2:0、8 bit か 10 bit）にする:

```sh
ffmpeg -i input.mp4 -t 10 -an -pix_fmt yuv420p -f yuv4mpegpipe out.y4m          # 8 bit
ffmpeg -i input.mp4 -t 10 -an -pix_fmt yuv420p10le -strict -1 -f yuv4mpegpipe out.y4m  # 10 bit
```

## 5. 時間を区切った速度計測（1 分 / 10 分）

```sh
export AVMDEC=$AVM_ROOT/_build_lib/avmdec      # PSNR を出すとき（省略すると速度だけ）
# 1 分: おおよその速度を見る
scripts/bench_time.py -i ~/clips/bbb_1080p60_10s.y4m --minutes 1  --out-dir runs/bbb_1min  -- --qindex 140
# 10 分: 報告に使う値
scripts/bench_time.py -i ~/clips/bbb_1080p60_10s.y4m --minutes 10 --out-dir runs/bbb_10min -- --qindex 140
```

`--` より後ろはそのまま celv2enc に渡る（`--qindex`、`--preset max`、`--workers`、
`--device cpu` など）。`--seconds 90` のように秒でも指定できる。

スクリプトがすること:

1. celv2enc を `--progress` 付きで起動し、`progress frame=N` の行が出た時刻を記録する
   （`--progress` のときは各フレームを書くたびに IVF をフラッシュするので、行が出た時点で
   そのフレームはファイルにある）
2. 制限時間で SIGTERM を送る（10 秒で終わらなければ SIGKILL）
3. IVF の最後の書きかけのフレームを切り落とし、ヘッダのフレーム数を直す
4. `--avmdec` があれば、書き出せたフレームを avmdec でデコードし、ffmpeg の psnr フィルタで
   元動画と比べる

出力（標準出力と `<out-dir>/summary.json`）:

| 項目 | 意味 |
|---|---|
| `frames_written` | 制限時間内に書き出せたフレーム数 |
| `first_frame_s` | 最初のフレーム（キーフレーム）が出るまでの秒数 |
| `fps` | `frames_written / 制限時間`。**下限**: 時間切れの時点で符号化中だったミニ GOP の分は数えない |
| `fps_last` | `frames_written / 最後のフレームを書いた時刻`。**上限寄り**: フレームはミニ GOP 単位でまとめて出てくるため |
| `frames_per_minute` | `fps × 60` |
| `kbps` | 書き出せたフレームのビットレート |
| `psnr_y` | 書き出せたフレームの輝度 PSNR（元動画のビット深度で計算） |

`<out-dir>` には他に `out.ivf`（切り落とし済み、avmdec でデコードできる）、`progress.csv`
（フレーム番号と秒）、`stderr.txt`（celv2enc の標準エラー）ができる。

### 1 分と 10 分の使い分け

celv2enc はキーフレームの後、ミニ GOP（既定では 4 フレーム。`--refs 5` 以上かつ `--qindex 100`
以上なら 8 フレーム）をまとめて符号化してから書き出す。CPU エンジンだとミニ GOP 1 つに数十秒〜
数分かかるので、1 分ではミニ GOP が 1 つか 2 つしか終わらず、`fps` と `fps_last` の差が大きい。

- **1 分**: 動くか、桁がどのくらいかを見る。条件をいくつも試すときのふるい分けに
- **10 分**: 報告する値。`fps` と `fps_last` の差が小さくなる
- 10 秒のクリップを最後まで符号化し終えた場合は `stopped_at_limit` が `false` になり、`fps` は
  そのまま全体の速度

### 計測のときの注意

- **他の重い処理と同時に走らせない。** 特に `scripts/test.sh` と並べると数倍遅く出る。
  `uptime` のロードアベレージで確認する
- 1 回だけの値はぶれる。条件を比べるときは同じ条件で 2〜3 回測る
- 計測中の CPU 使用率を見るには別の端末で `top -H -p $(pgrep -x celv2enc)`
- 時間のかかっている関数を見るには
  `sudo perf record -g -p $(pgrep -x celv2enc) -- sleep 10 && sudo perf report --no-children`

## 6. 条件を変えて比べる例

```sh
clip=~/clips/bbb_1080p60_10s.y4m
for q in 100 140 180; do
  scripts/bench_time.py -i $clip --minutes 10 --out-dir runs/bbb_q${q} -- --qindex $q
done
scripts/bench_time.py -i $clip --minutes 10 --out-dir runs/bbb_max  -- --qindex 140 --preset max
scripts/bench_time.py -i $clip --minutes 10 --out-dir runs/synth    -- --qindex 140   # 合成クリップ
```

結果を 1 つの表にまとめる:

```sh
python3 - runs/*/summary.json <<'EOF'
import json, sys
print('run,options,frames,fps,fps_last,kbps,psnr_y')
for p in sys.argv[1:]:
    r = json.load(open(p))
    print(','.join(str(x) for x in [p.split('/')[-2], ' '.join(r['options']), r['frames_written'],
                                    r['fps'], r['fps_last'], r['kbps'], r.get('psnr_y')]))
EOF
```

- `--workers N|auto` はシーン（キーフレームから次のキーフレームまで、48 フレーム以上）単位の
  並列化。10 秒のクリップはシーンが 1〜2 個なので効きにくい
- `--threads N` は CPU エンジンではタイル用スレッドの数だけを制限する（判定用スレッドは残りの
  コアを使う）

## 7. 記録用テンプレート

```
日付:
マシン: CPU / コア数 / メモリ / GPU
OS / コンパイラ:
celv2 のコミット:          git rev-parse --short HEAD
AVM:                        966a7d7 (v1.0.0)
エンジン:                   stderr.txt の "celv2: decisions on ..." の行
クリップ:
オプション:
制限時間:
frames_written / fps / fps_last:
kbps / psnr_y:
同時に動いていたもの:
```

## 8. この環境での結果（2026-11-01）

EPYC 7642 ×2（192 スレッド）、GPU なし（CPU エンジン）、`bbb_1080p60_10s.y4m`、`--qindex 140`、
他の負荷なし。

| 制限時間 | frames_written | first_frame_s | fps | fps_last | kbps | psnr_y |
|---|---|---|---|---|---|---|
| 1 分 | 5 | 0.5 | 0.083 | 0.23 | 16401 | 42.74 |
| 10 分 | 57 | 0.5 | 0.095 | 0.102 | 3715 | 45.37 |

1080p で毎秒 0.1 フレーム（1 分で約 6 フレーム）。1 分だと `fps` と `fps_last` が 3 倍近く開くが、
10 分ではほぼ一致する。1 分の kbps が高いのは、最初のキーフレームの比重が大きいため。参考までに、README では RTX 5090 と 24 コアの
Xeon で約 6 fps。

### 遅さの原因（perf で確認）

計測中、192 スレッドのうち 1 スレッドだけが 100% で、他はほぼ止まっていた。`perf` で見ると
そのスレッドの 98% が `build_pyramid_ref`（`src/gpu/kernels_ref.cpp`）だった。CPU エンジンは
フレームごとに、参照フレームそれぞれの 1/4 画素位相（16 位相 × 8 タップのフィルタを全画素に）を
**1 スレッドで作り直している**（`CpuEngine::launch`、前のフレームで作ったものも再利用しない）。
この間、動き探索と判定のワーカースレッドは始まっていない。

これは Linux 移植で入ったものではなく、元の CPU エンジンの作りによるもの。位相の計算を行で
分けて並列にする、参照フレームのピラミッドを `ref_keys` で使い回す（GPU エンジンと同じ）と
いった変更なら出力のバイト列を変えずに速くできる見込みがある。
