#!/usr/bin/env bash
# ============================================================================
# extract_scene_frames.sh — 按场景变化抽取带时间戳的代表帧
#
# 用途：从任意视频侦测明显场景变化，抓取代表帧，文件名内嵌毫秒时间戳，并输出
# frames.json 清单。可用于前期内容画像，也可在最终时间轴上把画面文字与字幕对齐。
#
# 用法：
#   scripts/extract_scene_frames.sh <视频> <输出目录> [scene阈值(0-1)]
# 例（校对剪辑后字幕时，必须从同时间轴的 edited.mp4 抽帧）：
#   scripts/extract_scene_frames.sh edited.mp4 scene_frames/ 0.3
#
# 可调环境变量（不写死，按片子实测调）：
#   MIN_GAP=0.8       相邻换页点的最小间隔（秒），只用来压掉“同页构建动画/连击”的亚秒级重触发
#   GRAB_OFFSET=0.5   切换后延迟多少秒再抓帧，避开转场动画的中间糊帧（必须 < MIN_GAP，否则会串到下一页）
#   DETECT_FPS=4      侦测趟先把帧率降采样到多少 fps 再算 scene 差分（提速，不影响时间戳精度到秒）
#   DETECT_W=640      侦测趟缩到的宽度（差分更便宜、顺带压掉传感器噪声）
#
# 平台：macOS / Linux / WSL2 直接可跑。原生 Windows（Git Bash/MSYS2）建议改走 WSL2——
# filtergraph 里的 metadata=print:file= 路径在原生 ffmpeg.exe 下未验证（跟步骤 5 subtitles 同类坑）。
#
# 设计要点见文件内注释：为什么两趟、为什么补 t=0、为什么用连字符命名、为什么全程只碰“秒”。
# ============================================================================
set -euo pipefail
export LC_ALL=C   # 钉死数字 locale：逗号小数制(de_DE/fr_FR/CI)下 awk 会把 1.5 解析成 1、
                  # printf 输出逗号，导致时间戳被截断、frames.json 变非法 JSON。一行修好三处(解析/打印/sort)。

# ---- 参数 ------------------------------------------------------------------
INPUT="${1:?用法: extract_scene_frames.sh <视频> <输出目录> [scene阈值(0-1)]}"
OUTDIR="${2:?需要输出目录}"
THRESH="${3:-0.3}"                 # scene 分阈值(0-1)。稳定屏幕 0.2-0.3；混合画面 0.3；运动实拍 0.4-0.5
MIN_GAP="${MIN_GAP:-0.8}"          # 只合并 <1s 的动画/连切重触发；保持亚秒级以避免吞掉短暂场景。
GRAB_OFFSET="${GRAB_OFFSET:-0.5}"  # 切换后延迟抓帧，避开转场糊帧（秒）
DETECT_FPS="${DETECT_FPS:-4}"      # 侦测趟降采样帧率
DETECT_W="${DETECT_W:-640}"        # 侦测趟降采样宽度

# 输入必须存在：否则侦测趟的 `|| true` 会吞掉错误、退化成只抓 t=0、抓帧再失败，
# 最终静默产出空 [] 还 exit 0——这正是本 skill 反复强调要避免的“静默失败/留下看似存在其实是坏的产物”。
[ -f "$INPUT" ] || { echo "输入文件不存在: $INPUT" >&2; exit 1; }

# ---- ffmpeg / ffprobe 选择：不写死路径 --------------------------------------
# macOS 上优先用 Homebrew 的 ffmpeg-full（跟本 skill 其余步骤一致，避开 libvpx 冲突后
# 到处找不到滤镜的问题）；让 brew 自己给前缀，别写死 /usr/local/opt(Intel) 或
# /opt/homebrew/opt(Apple Silicon)。Linux/WSL2/原生 Windows 一律走 PATH 里的 ffmpeg。
case "$(uname -s)" in
  Darwin)
    _pfx="$( { brew --prefix ffmpeg-full 2>/dev/null || true; } )"   # brew 不存在也不炸脚本
    FFMPEG="${_pfx}/bin/ffmpeg"
    [ -x "$FFMPEG" ] || FFMPEG="ffmpeg"                              # 没装 full 就退回 PATH
    ;;
  *)
    # Linux / WSL2（uname 都是 Linux）/ 原生 Windows Git Bash（MINGW*/MSYS*）统一走 PATH
    FFMPEG="ffmpeg"
    ;;
esac
command -v "$FFMPEG" >/dev/null 2>&1 || { echo "找不到 ffmpeg: $FFMPEG" >&2; exit 1; }

# ffprobe 取同目录的兄弟（$FFMPEG 是完整路径时），否则退回 PATH。ffprobe 缺失不致命，
# 只是拿不到时长、跳过“抽帧密度过高”的护栏告警。
FFPROBE="${FFMPEG%ffmpeg}ffprobe"
[ -x "$FFPROBE" ] || FFPROBE="ffprobe"
command -v "$FFPROBE" >/dev/null 2>&1 || FFPROBE=""

mkdir -p "$OUTDIR"

# scratch 目录：mktemp -d 给的是纯 ASCII、无空格的路径（/tmp/... 或 macOS 的
# /var/folders/...）。侦测趟的 metadata=print:file= 那个路径在 filtergraph 内部，
# 空格/中文/冒号都会被当成分隔或转义字符导致解析失败——所以场景文件必须落在这里，
# 而不是 OUTDIR（用户给的输出目录很可能带中文/空格）。这跟步骤 5 subtitles 滤镜同一类坑。
SCRATCH="$(mktemp -d)"; trap 'rm -rf "$SCRATCH"' EXIT
SCENES_TXT="$SCRATCH/scenes.txt"
TIMES_RAW="$SCRATCH/times_raw.txt"
TIMES_FINAL="$SCRATCH/times_final.txt"
ENTRIES="$SCRATCH/entries.jsonl"

# ---- 侦测趟的能力探测（先落文件再 grep，避免 pipefail 下的 SIGPIPE 坑）--------
# 坑：`ffmpeg ... | grep -q X` 里 grep -q 命中后提前退出，会给上游 ffmpeg 发 SIGPIPE，
# 在 set -euo pipefail 下 ffmpeg 以 141 退出、pipefail 取到这个非零值，整条判断莫名失败。
# 对策：先把输出重定向进 SCRATCH 里的文件，再对文件 grep，管道里不再有会被 SIGPIPE 打断的进程。
"$FFMPEG" -hide_banner -h full > "$SCRATCH/ffmpeg_help.txt" 2>&1 || true
if grep -q -- '-fps_mode' "$SCRATCH/ffmpeg_help.txt"; then
  FPS_MODE="-fps_mode vfr"    # 新版 ffmpeg 写法
else
  FPS_MODE="-vsync vfr"       # 老版本回退（仍可用，只是会告警）
fi

# ---- 第 1 趟：只侦测换页时间戳，不出帧（-f null -）--------------------------
# 为什么两趟：一趟 select 直接出图时 ffmpeg 只能用顺序编号 %d，你拿到 img001.jpg 却不知道
# 它对应第几秒，跟字幕时间轴对不上。拆成两趟后，第 1 趟只导出干净的“秒”，第 2 趟按秒定点抓帧。
#
# 为什么用 select='gt(scene,T)'（而不是 scdet）：select 会把没达到阈值的帧丢掉，metadata=print
# 只打印真正的换页帧，SCENES_TXT 干净。scdet 不丢帧，配 metadata=print 会把每一帧都打印出来
# （降采样后仍上万行），反而抓不出换页点——所以这里坚持用 select+scene，正确性优先。
#
# 为什么用 metadata=print:file= 而不是 showinfo：showinfo 把信息灌进 stderr 跟一堆日志噪声混在
# 一起，难解析；metadata=print 单独写一个干净文件。
#
# 为什么先 fps + scale 降采样：长视频逐帧计算 scene 分很慢，先抽到 4fps、缩到宽 640
# 再算差分，解码量降一个量级，对代表场景检测通常足够（时间戳仍是真实秒，只是精度落到 1/fps 秒）。
# scale 的 -2 保证高度为偶数（libx264/编码器要求），别写死具体高度。
#
# VFR（可变帧率）在本步天然免疫：全程只用“秒”（pts_time、-ss <秒>），从不碰帧号，
# 这跟步骤 3 里 select 依赖准确 FRAME_RATE 的情况不同。-c copy 在这里也根本不适用——
# scene 侦测必须完整解码像素，流拷贝拿不到帧内容。
"$FFMPEG" -hide_banner -nostdin -an -sn -i "$INPUT" \
  -vf "fps=${DETECT_FPS},scale=${DETECT_W}:-2,select='gt(scene\,${THRESH})',metadata=print:file=${SCENES_TXT}" \
  $FPS_MODE -f null - >/dev/null 2>&1 || true   # 侦测失败(空结果等)不致命，后面退化护栏兜底

# 解析出换页时间列表（秒）。grep 无命中时返回 1，pipefail 下会让整条管道失败，故 || true 兜底；
# > 会保证 TIMES_RAW 即便为空也存在（单页视频没有任何换页点是正常情况，不能报错退出）。
grep -Eo 'pts_time:[0-9.]+' "$SCENES_TXT" 2>/dev/null | cut -d: -f2 > "$TIMES_RAW" || true
[ -f "$TIMES_RAW" ] || : > "$TIMES_RAW"

# ---- 补 t=0 首帧 + 排序 + 近邻合并 ----------------------------------------
# 为什么必须补 t=0：scene 滤镜对第一帧输出 0 分（没有“上一帧”可比），开场画面永远
# 触发不了 gt(scene,T)，不补就漏首个场景。
# 为什么用 awk 不用 bc：bc 在精简系统/Git Bash 里未必有；浮点比较全走 awk，跨平台无依赖。
#
# 关键：近邻合并只在“侦测到的换页点”之间做，起始 last 置成极小值（不是 0），千万别拿 t=0
# 去参与合并。否则若第一张只放到 1.5s 就翻页，1.5s 这个真实换页点会因“距 0 太近”被 t=0 吞掉，
# 第二个场景就丢了。这里的取舍是：t=0 永远单独保留，检测点从头独立合并——代价是开场偶尔
# 多出一张与首帧近乎重复的帧（冗余），但尽量不漏短暂场景。最后与 t=0 合并、排序、去掉重复的 0。
{
  echo 0                                          # t=0 无条件保留(scene 对首帧输出 0 分，永远触发不了)
  sort -n "$TIMES_RAW" | awk -v gap="$MIN_GAP" '
    BEGIN{last=-1e18}                             # 极小起点：保证第一个检测点一定保留，不被 0 吞
    {t=$1+0}
    t-last>=gap{printf "%.6f\n", t; last=t}       # 距上一个保留的检测点 >= MIN_GAP 才留，否则丢弃(合并连击)
  '
} | sort -n | awk '!seen[$0]++' > "$TIMES_FINAL"   # 合并并按时间排序，去掉可能重复的 0

# 退化护栏：全程无明显场景变化时 TIMES_RAW 为空 → 合并后至少要留下 t=0 这一帧。
# 关键不变量：无论如何至少产出 t=0，绝不因“没检测到换页”而报错退出——这跟文末
# “keep_segments 为空要报错”是相反的诉求（那里空了是异常，这里空了是单页视频，属正常）。
[ -s "$TIMES_FINAL" ] || echo 0 > "$TIMES_FINAL"

N="$(wc -l < "$TIMES_FINAL" | tr -d '[:space:]')"
echo "共 ${N} 张代表帧（阈值 ${THRESH}，合并间隔 ${MIN_GAP}s，侦测降采样 ${DETECT_FPS}fps/${DETECT_W}px）" >&2

# 抽帧密度护栏：密度异常高基本是把讲者走动/镜头切当成了换页，应提示调阈值，而不是默默塞几百张废图。
# 只对“张数够多的长视频”告警（N>10），避免短的单页视频被误报（6s 单页=10 张/分钟但只有 1 张，不算异常）。
if [ -n "$FFPROBE" ] && [ "$N" -gt 10 ]; then
  DURATION="$("$FFPROBE" -v error -show_entries format=duration \
              -of default=noprint_wrappers=1:nokey=1 "$INPUT" 2>/dev/null || true)"
  if [ -n "${DURATION:-}" ]; then
    PERMIN="$(awk -v n="$N" -v d="$DURATION" 'BEGIN{ if(d>0) printf "%.2f", n/(d/60); else print "0" }')"
    if awk -v p="$PERMIN" 'BEGIN{ exit !(p>6) }'; then
      echo "警告：抽帧密度 ${PERMIN} 张/分钟 偏高，视频可能运动/切换密集，或 scene 阈值过低。" >&2
      echo "      建议调高阈值（如 0.4/0.5），或改用固定间隔抽样完成内容画像。" >&2
    fi
  fi
fi

# ---- 第 2 趟：定点抓帧 + 文件名内嵌时间戳 --------------------------------
# 为什么 -ss 放在 -i 前：现代 ffmpeg 的输入端 seek 既快又精确（先跳到关键帧再解码到目标点），
# 对 VFR 也安全；放 -i 后是从头解码到目标点，几十个点会奇慢。
# 为什么 -nostdin：抓帧的 while 循环从 TIMES_FINAL 读 stdin，不加 -nostdin 的话 ffmpeg 会
# 把循环剩下的行当自己的标准输入吞掉，循环只跑一次就结束。
# 文件名 frame_<9位毫秒>_<HH-MM-SS-mmm>.jpg：
#   - 前段 9 位零填充毫秒：保证“字典序 = 时间序”，ls 直接有序（覆盖约 277 小时，够长）。
#   - 后段 HH-MM-SS-mmm：人眼可读，且和 SRT 的 HH:MM:SS,mmm 一一对应，方便按时间轴对字幕条。
#   - 用连字符不用冒号：冒号在 Windows/exFAT 上是非法文件名字符，会在原生 Windows 上直接写不出文件。
: > "$ENTRIES"
while read -r t || [ -n "$t" ]; do          # `|| [ -n "$t" ]` 兜底：末行无换行也不漏最后一张
  [ -n "$t" ] || continue
  # 抓帧点 = 切换时刻 + GRAB_OFFSET（合并后相邻间隔 >= MIN_GAP，且 GRAB_OFFSET < MIN_GAP，不会串到下一页）
  grab="$(awk -v t="$t" -v o="$GRAB_OFFSET" 'BEGIN{printf "%.3f", t+o}')"
  # 毫秒：先算总毫秒(四舍五入)再用它拆分时分秒，别先截断秒再单独 round 毫秒——否则浮点误差
  # 会让 1.9996s 变成 00-00-01-1000（4 位毫秒，非法），这是本 skill 文末点过名的坑。
  ms="$(awk -v t="$t" 'BEGIN{printf "%d", t*1000+0.5}')"
  hms="$(awk -v ms="$ms" 'BEGIN{
           tot=ms; h=int(tot/3600000); tot%=3600000;
           m=int(tot/60000); tot%=60000; s=int(tot/1000); mm=tot%1000;
           printf "%02d-%02d-%02d-%03d", h, m, s, mm }')"
  fname="frame_$(printf '%09d' "$ms")_${hms}.jpg"
  out="${OUTDIR}/${fname}"
  tsec="$(awk -v ms="$ms" 'BEGIN{printf "%.3f", ms/1000}')"   # frames.json 里的起始秒(与文件名同源)

  # 输出帧路径 "$out" 在 filtergraph 之外，普通 shell 引号即可，含空格/中文无妨。
  if "$FFMPEG" -hide_banner -nostdin -ss "$grab" -i "$INPUT" -frames:v 1 -q:v 2 -y "$out" >/dev/null 2>&1; then
    printf '  {"t": %s, "frame": "%s"}\n' "$tsec" "$fname" >> "$ENTRIES"
    echo "抓帧 @${t}s -> $out" >&2
  else
    echo "跳过 @${t}s（抓帧失败，已忽略）" >&2
  fi
done < "$TIMES_FINAL"

NW="$(wc -l < "$ENTRIES" | tr -d '[:space:]')"
# 一帧都没抓到 = 输入损坏/无视频流/全部 -ss 越界，是异常，必须报错（而不是像单页视频那样静默产出 1 帧）。
# 单页视频至少有 t=0 那帧(NW>=1)，与此可区分；别留下一个合法路径却指向空 [] 的产物骗过调用方。
[ "$NW" -gt 0 ] || { echo "错误：一帧都没抓到（输入损坏/无视频流/时间戳全部越界）" >&2; exit 1; }

# ---- 输出 frames.json 清单 -------------------------------------------------
# 形如 [{"t": 12.320, "frame": "frame_000012320_00-00-12-320.jpg"}, ...]
# 校对时按 t（或文件名里的 HH-MM-SS-mmm）定位到最终 SRT 中同时间窗的字幕条，用清晰画面文字
# 辅助确认拼写和专名。画面不是逐字稿，只纠正有证据的词，不改写说话内容。
# 文件名全是 ASCII，JSON 里不需要额外转义。
JSON="${OUTDIR}/frames.json"
{
  echo "["
  # 用 awk 在“行与行之间”插逗号，末行不加，得到合法 JSON 数组
  awk 'NR>1{printf ",\n"} {printf "%s", $0} END{if(NR>0) printf "\n"}' "$ENTRIES"
  echo "]"
} > "$JSON"

echo "完成：实际抓到 ${NW} 张，清单写入 ${JSON}" >&2
echo "$JSON"    # stdout 只打印清单路径，方便 $(...) 取用；诊断信息都走 stderr
