#!/usr/bin/env bash
# Detect available compute (Apple Metal / NVIDIA CUDA / CPU-only) and RAM/VRAM,
# pick the largest ggml whisper model that should still transcribe in a
# reasonable time on this machine, and download it into ~/whisper-models if
# not already present. All diagnostic output goes to stderr; the last line on
# stdout is the model file path, so callers can do:
#   MODEL=$(scripts/pick_whisper_model.sh)
#
# Usage: scripts/pick_whisper_model.sh
# Optional env:
#   WHISPER_MODEL_TIER=<tiny|small|medium|large-v3>  skip all detection, force this tier.
#     Use this for hardware the auto-detection can't see correctly: NVIDIA Jetson
#     (no nvidia-smi binary, uses tegrastats instead), AMD/ROCm GPUs (this script
#     only knows how to query nvidia-smi), or a cgroup/Docker-quota-limited CPU
#     count that `nproc` can't see (nproc reports the host's raw core count, not
#     the container's throttled quota, so auto-picked tiers can be too big for
#     CI/containers). Also the simplest fix if you already know better than the
#     heuristics below.
#   WHISPER_ASSUME_CUDA=1  on Linux/Windows, trust VRAM-based tiering enough to
#     pick large-v3 (see note below) -- only relevant if WHISPER_MODEL_TIER is unset.
#   WHISPER_MODEL_DIR  change the model download location (default ~/whisper-models).
set -euo pipefail

MODEL_DIR="${WHISPER_MODEL_DIR:-$HOME/whisper-models}"
mkdir -p "$MODEL_DIR"

os="$(uname -s)"
arch="$(uname -m)"

# Query total VRAM in whole GB via nvidia-smi. Never raises under `set -e`:
# `|| raw=""` catches a broken/absent binary, WSL without GPU passthrough, and
# SIGPIPE from `head -1` on multi-GPU hosts (pipefail would otherwise abort the
# whole script). `tr -d '\r'` strips the trailing CR that nvidia-smi.exe (a
# native Windows console app opened in CRT text mode) emits even when its
# output is piped/redirected rather than printed to a real console -- without
# this, Git Bash's `head` passes the "12288\r" through untouched, the regex
# below (anchored with $) fails on the stray \r, and a real GPU gets reported
# as "not detected". The regex also catches non-numeric replies like "[N/A]"
# or "[Insufficient Permissions]" that nvidia-smi prints for MIG/virtualized/
# permission-restricted GPUs -- those are treated as "unknown", not as 0GB.
detect_vram_gb() {
  local raw
  raw="$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -n1 | tr -d '\r')" || raw=""
  if [[ "$raw" =~ ^[0-9]+$ ]]; then
    echo $(( raw / 1024 ))
  else
    echo ""
  fi
}

tier=medium
accel="cpu-only（预计较慢，medium 在 CPU 上可能接近或慢于实时）"

if [[ -n "${WHISPER_MODEL_TIER:-}" ]]; then
  tier="$WHISPER_MODEL_TIER"
  accel="手动指定 WHISPER_MODEL_TIER=${tier}，跳过硬件检测"

elif [[ "$os" == "Darwin" && "$arch" == "arm64" ]]; then
  # Apple Silicon: brew 装的 whisper-cpp 默认编译时就带 Metal，会自动用 GPU，
  # 不需要任何额外参数去“开启”它——这里只是根据统一内存大小判断能不能扛得住
  # 更大的模型档位（模型权重 + KV cache 都要吃内存，内存不够会 OOM 或疯狂 swap）。
  mem_bytes="$(sysctl -n hw.memsize)"
  mem_gb=$(( mem_bytes / 1024 / 1024 / 1024 ))
  if   (( mem_gb >= 32 )); then tier=large-v3
  elif (( mem_gb >= 16 )); then tier=medium
  else                          tier=small
  fi
  accel="Apple Silicon Metal GPU 加速（whisper-cpp 默认编译自带，无需额外配置），统一内存 ${mem_gb}GB"

elif [[ "$os" == "Darwin" ]]; then
  # Intel Mac：whisper.cpp 没有可用的 GPU 加速路径（旧的 OpenCL 支持已废弃），纯 CPU 跑，
  # 只能靠核数判断能不能扛住 medium。`hw.ncpu` 是逻辑线程数（开了超线程的 Xeon
  # 上是物理核数的两倍），阈值判断按线程数算没问题，只是消息里别说成"核"误导。
  cores="$(sysctl -n hw.ncpu)"
  if (( cores >= 8 )); then tier=medium; else tier=small; fi
  accel="Intel Mac，无 GPU 加速可用，纯 CPU（${cores} 线程）"

elif [[ "$os" == MINGW* || "$os" == MSYS* || "$os" == CYGWIN* ]]; then
  # 原生 Windows，脚本跑在 Git Bash / MSYS2 里（`uname -s` 是 MINGW64_NT-.../MSYS_NT-...）。
  # 如果是 WSL，`uname -s` 会显示 "Linux"，走的是下面 Linux 那个分支，不会进这里。
  vram_gb=""
  if command -v nvidia-smi >/dev/null 2>&1; then
    vram_gb="$(detect_vram_gb)"
  fi
  if [[ -n "$vram_gb" ]]; then
    # 检测到显卡且拿到了显存数值，不代表真能加速：官方预编译版/自己编译的
    # whisper.cpp 是否带 cuBLAS/CUDA 支持因发行版而异，默认按"大概率没有"处理，
    # 只在 small/medium 间选，避免白等一个用不上 GPU 的 large-v3。确认自己装的是
    # CUDA 编译版，可以设 WHISPER_ASSUME_CUDA=1 重跑来解锁 large-v3。
    if [[ -n "${WHISPER_ASSUME_CUDA:-}" ]]; then
      if   (( vram_gb >= 10 )); then tier=large-v3
      elif (( vram_gb >= 6  )); then tier=medium
      else                           tier=small
      fi
      cuda_note="WHISPER_ASSUME_CUDA=1，按显存直接选档"
    else
      if (( vram_gb >= 6 )); then tier=medium; else tier=small; fi
      cuda_note="未设 WHISPER_ASSUME_CUDA，默认当作没有 CUDA 加速，只在 small/medium 间选"
    fi
    accel="Windows（Git Bash/MSYS），检测到 NVIDIA GPU（显存 ${vram_gb}GB），${cuda_note}"
  else
    cores="${NUMBER_OF_PROCESSORS:-$(nproc 2>/dev/null || echo 4)}"
    if (( cores >= 8 )); then tier=medium; else tier=small; fi
    accel="Windows（Git Bash/MSYS），未检测到可用的 NVIDIA GPU 信息，纯 CPU（${cores} 线程）"
  fi
  echo "注意：1) 其余步骤（bash 脚本、python3、ffmpeg 命令）假定类 Unix shell 环境，完整流程建议在 WSL 里跑，Git Bash 只保证这一步模型选择能跑；2) 原生 Windows 没有 brew，whisper-cli 需要去 https://github.com/ggml-org/whisper.cpp/releases 下载预编译版或自己编译，本脚本只负责选模型、不负责装 whisper-cli" >&2

elif command -v nvidia-smi >/dev/null 2>&1 && vram_gb="$(detect_vram_gb)" && [[ -n "$vram_gb" ]]; then
  # Linux（含 WSL2，只要装了 NVIDIA 的 WSL 直通驱动 nvidia-smi 就能查到）+ NVIDIA
  # 且拿到了有效显存数值：homebrew 装的 whisper-cpp 默认不带 CUDA 编译选项，检测到
  # 显卡不代表真的会用上——真正吃到 GPU 加速需要从源码重新编译（cmake -DGGML_CUDA=ON），
  # 默认按"大概率没有 CUDA"处理，只在 small/medium 间选；确认自己编译过 CUDA 版可以设
  # WHISPER_ASSUME_CUDA=1 解锁 large-v3。
  if [[ -n "${WHISPER_ASSUME_CUDA:-}" ]]; then
    if   (( vram_gb >= 10 )); then tier=large-v3
    elif (( vram_gb >= 6  )); then tier=medium
    else                           tier=small
    fi
    cuda_note="WHISPER_ASSUME_CUDA=1，按显存直接选档"
  else
    if (( vram_gb >= 6 )); then tier=medium; else tier=small; fi
    cuda_note="未设 WHISPER_ASSUME_CUDA，默认当作没有 CUDA 加速，只在 small/medium 间选；如需真正 GPU 加速需要从源码重新编译（cmake -DGGML_CUDA=ON），这一步跟用户确认后再做，本脚本不自动编译"
  fi
  accel="检测到 NVIDIA GPU（显存 ${vram_gb}GB，Linux/WSL2），${cuda_note}"

else
  # 这条分支只是"没查到 nvidia-smi"，不代表这台机器真的没有 GPU：AMD/ROCm 显卡、
  # NVIDIA Jetson（用 tegrastats/jtop 不是 nvidia-smi）这类硬件本脚本都识别不了，
  # 会被当成纯 CPU 处理——如果你确定自己的硬件能扛更大的模型，直接设
  # WHISPER_MODEL_TIER 跳过检测（见文件顶部注释），不用等这里判断准。
  # `nproc` 在 cgroup/Docker --cpus 限流的容器里也会报宿主机的真实核数而不是
  # 配额，CI 里与其等这里猜，不如显式设 WHISPER_MODEL_TIER 钉死一个档位。
  cores="$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)"
  if (( cores >= 8 )); then tier=medium; else tier=small; fi
  accel="未检测到 NVIDIA GPU（或 nvidia-smi 查询失败/无权限；AMD/ROCm、Jetson 等硬件本脚本无法识别，不代表真没有 GPU），纯 CPU（${cores} 线程）"
fi

echo "硬件检测：$accel" >&2
echo "选定模型档位：$tier" >&2

model_file="$MODEL_DIR/ggml-${tier}.bin"
if [[ ! -f "$model_file" ]]; then
  # large-v3 约 3GB，small/medium 也有几百 MB 到 1.5GB，下载前提示一下剩余空间
  # （只是警告，不阻断——`df` 在极少数环境里可能不可用或格式不同，解析失败就跳过）。
  avail_kb="$(df -Pk "$MODEL_DIR" 2>/dev/null | tail -1 | awk '{print $4}')" || avail_kb=""
  if [[ "$avail_kb" =~ ^[0-9]+$ ]]; then
    avail_gb=$(( avail_kb / 1024 / 1024 ))
    if (( avail_gb < 4 )); then
      echo "警告：$MODEL_DIR 所在磁盘剩余空间约 ${avail_gb}GB，可能不够下载 $tier 模型，注意检查" >&2
    fi
  fi

  echo "模型文件不存在，下载 $model_file ..." >&2
  tmp_file="${model_file}.part"
  # --fail：HTTP 4xx/5xx 时非 0 退出，不会把错误页面内容当模型文件存下来；
  # 下载到 .part 再 mv：网络中途断开也不会留下一个"文件存在但其实是半截"的
  # 产物——否则下次运行时 [[ ! -f "$model_file" ]] 会误判为"已下载过"直接跳过，
  # whisper-cli 会一直加载这个损坏文件。
  if ! curl --fail -L -o "$tmp_file" \
      "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-${tier}.bin"; then
    rm -f "$tmp_file"
    echo "下载失败：$model_file 未生成，检查网络/磁盘空间后重跑本脚本即可重试" >&2
    exit 1
  fi
  mv "$tmp_file" "$model_file"
fi

echo "$model_file"
