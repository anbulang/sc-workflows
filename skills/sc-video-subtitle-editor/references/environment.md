# 环境、模型与跨平台说明

只在依赖缺失、模型选择异常或平台兼容问题出现时读取本文件。

## 目录

1. 依赖检查原则
2. macOS
3. Linux 与 WSL2
4. 原生 Windows
5. 模型选择
6. 长尾硬件与下载护栏

## 1. 依赖检查原则

先运行 `uname -s` 和 `uname -m`。安装软件、编译 whisper.cpp 或修改系统包之前先征得用户许可。
不要把 macOS 的 Homebrew 命令复制到 Linux/Windows，也不要写死 Intel 或 Apple Silicon 的前缀。

需要：

- `ffmpeg` / `ffprobe`；硬字幕需要带 libass `subtitles` 滤镜的构建。
- `whisper-cli`（whisper.cpp）。
- Python 3 和 Bash；原生 Windows 推荐使用 WSL2。

## 2. macOS

```bash
which whisper-cli || brew install whisper-cpp
"$(brew --prefix ffmpeg-full 2>/dev/null)/bin/ffmpeg" -filters 2>&1 | grep subtitles \
  || brew install ffmpeg-full
```

用 `brew --prefix ffmpeg-full` 取得实际前缀；不要写死 `/usr/local/opt` 或 `/opt/homebrew/opt`。
`ffmpeg-full` 安装升级 `libvpx` 后，独立 `ffmpeg` 可能因动态库版本失配而失败；可在用户同意后
`brew reinstall ffmpeg`，或全程使用 `"$(brew --prefix ffmpeg-full)/bin/ffmpeg"`。

## 3. Linux 与 WSL2

使用发行版包管理器安装 ffmpeg。Debian/Ubuntu 示例：

```bash
which ffmpeg || sudo apt-get install -y ffmpeg
```

whisper-cli 通常需要从源码编译：

```bash
git clone https://github.com/ggml-org/whisper.cpp
cd whisper.cpp
cmake -B build
cmake --build build --config Release
```

只有用户确认已编译 CUDA 支持时才使用 `-DGGML_CUDA=ON` 或设置
`WHISPER_ASSUME_CUDA=1`。检测到 NVIDIA 显卡不等于 whisper.cpp 实际支持 CUDA。

## 4. 原生 Windows

Git Bash/MSYS2 的 `uname -s` 通常为 `MINGW*`/`MSYS*`。ffmpeg 可使用可信的 Windows 构建，
whisper-cli 可使用 whisper.cpp 发布的预编译版本或自行编译。完整流程更推荐 WSL2，因为 Bash、
Python、ffmpeg filtergraph 路径和字幕滤镜在类 Unix 环境中更稳定。

## 5. 模型选择

不要写死模型档位，运行：

```bash
MODEL=$(bash scripts/pick_whisper_model.sh)
echo "$MODEL"
```

脚本根据硬件选择 `small`、`medium` 或 `large-v3`，下载到
`${WHISPER_MODEL_DIR:-$HOME/whisper-models}`，并将模型路径作为 stdout 最后一行输出。

- Apple Silicon：Metal 通常随 brew 构建自动启用，主要按统一内存分档。
- Intel Mac：按 CPU 线程数分档。
- Linux/Windows + NVIDIA：默认不假设 CUDA 构建，只在 `small`/`medium` 间选择；确认 CUDA
  构建后设置 `WHISPER_ASSUME_CUDA=1` 才允许选择 `large-v3`。
- 已知硬件情况时可设置 `WHISPER_MODEL_TIER=<tiny|small|medium|large-v3>` 跳过检测。

`-t` 线程数通常取可用逻辑线程的约 3/4，同时给系统和编码留余量。容器中要按实际 CPU 配额，
不要盲信宿主机的 `nproc`。

## 6. 长尾硬件与下载护栏

AMD/ROCm、Jetson、MIG、受限容器和无权限的 `nvidia-smi` 可能无法自动识别；直接用
`WHISPER_MODEL_TIER` 固定档位。`nvidia-smi` 查询失败、返回 `[N/A]` 或多 GPU 管道 SIGPIPE
都必须降级处理，不能让 `set -euo pipefail` 终止脚本。

模型下载必须使用 `curl --fail`，先写 `.part`，成功后再 `mv`；失败时删除临时文件，不能留下
被误判为完整模型的错误页面或半截文件。下载大模型前检查磁盘空间。
