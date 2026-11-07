"""
Retime an SRT file to match a video that's been cut down to `keep` segments
(as produced by build_edl.py). Each original entry's start/end timestamp is
mapped through cumulative kept-duration; timestamps falling inside a removed
gap are clamped forward to the next kept segment's start.

Usage: python3 retime_srt.py <original.srt> <keep_segments.json> <output.srt>
"""
import json, re, sys

def build_map_time(keep):
    if not keep:
        raise ValueError("keep_segments is empty -- nothing survives the cut, check build_edl.py output")
    cum = 0.0
    table = []
    for s, e in keep:
        table.append((s, e, cum))
        cum += (e - s)
    total = cum

    def map_time(t):
        for s, e, cum_before in table:
            if t < s:
                return cum_before
            if s <= t <= e:
                return cum_before + (t - s)
        return total
    return map_time

def parse_srt(path):
    content = open(path, encoding="utf-8").read()
    blocks = re.split(r'\n\s*\n', content.strip())
    entries = []
    skipped = 0
    for b in blocks:
        lines = b.strip().split("\n")
        if len(lines) < 2:
            skipped += 1
            continue
        m = re.match(r'(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)', lines[1])
        if not m:
            skipped += 1
            continue
        h1,m1,s1,ms1,h2,m2,s2,ms2 = map(int, m.groups())
        start = h1*3600+m1*60+s1+ms1/1000
        end = h2*3600+m2*60+s2+ms2/1000
        text = "\n".join(lines[2:])
        entries.append({"start": start, "end": end, "text": text})
    if skipped:
        print(f"WARNING: {skipped} block(s) in {path} did not parse as valid SRT entries and were silently dropped -- check for manual edits / malformed timestamps", file=sys.stderr)
    return entries

def fmt_ts(t):
    if t < 0: t = 0
    # round the total millisecond count first, then split -- rounding ms
    # separately after truncating seconds can carry over to 1000ms (e.g.
    # t=1.9996 -> s=1, ms=round(999.6)=1000 -> invalid "00:00:01,1000").
    total_ms = int(round(t * 1000))
    h, rem = divmod(total_ms, 3600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

if __name__ == "__main__":
    keep = json.load(open(sys.argv[2]))
    map_time = build_map_time(keep)
    entries = parse_srt(sys.argv[1])

    out = []
    dropped = 0
    for e in entries:
        ns, ne = map_time(e["start"]), map_time(e["end"])
        if ne - ns < 0.05:
            dropped += 1
            continue
        out.append({"start": ns, "end": ne, "text": e["text"]})

    print(f"{len(entries)} original entries -> {len(out)} kept, {dropped} dropped (fully inside a cut)")

    with open(sys.argv[3], "w", encoding="utf-8") as f:
        for i, e in enumerate(out, 1):
            f.write(f"{i}\n{fmt_ts(e['start'])} --> {fmt_ts(e['end'])}\n{e['text']}\n\n")
