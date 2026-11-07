"""
Turn a list of user-approved cut candidates (from find_edit_candidates.py,
filtered to the exact items the user approved) into the complementary "keep"
segments used both for the ffmpeg
select/aselect cut and for retime_srt.py.

Usage: python3 build_edl.py <approved_cuts.json> <video_duration_seconds> <output_keep.json>

approved_cuts.json: [{"from": ms, "to": ms, "type": "long_silence"|"filler_word"|...}, ...]
(extra keys beyond from/to/type ignored)
"""
import json, sys

# Leave a small breathing gap at each cut instead of splicing frame-to-frame --
# an edit with zero gap around long silences reads as an unnaturally abrupt
# jump-cut. Shrinks each cut interval by this much on both sides (never
# inverts a short cut: capped at 40% of its own length).
#
# Only applied to long_silence cuts. filler_word cuts are short on purpose
# (a "嗯"/"啊" token is typically 0.2-0.5s) and the whole point is to remove
# the word -- padding a 0.3s filler cut by 0.12s on each side leaves only
# ~60ms actually cut, so most of the word's audio survives while the matching
# character has already been stripped from the subtitle text, producing an
# audio/subtitle mismatch.
PAD_S = 0.3
PADDED_TYPES = {"long_silence"}

def build_keep_segments(cuts, duration_s, pad_s=PAD_S):
    intervals = []
    for c in cuts:
        s, e = c["from"] / 1000, c["to"] / 1000
        if e <= s:
            continue
        if pad_s and c.get("type") in PADDED_TYPES:
            p = min(pad_s, (e - s) * 0.4)
            s, e = s + p, e - p
        intervals.append((s, e))
    intervals.sort()
    merged = []
    for s, e in intervals:
        if merged and s <= merged[-1][1] + 0.05:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))

    keep = []
    cursor = 0.0
    for s, e in merged:
        if s > cursor:
            keep.append((cursor, s))
        cursor = max(cursor, e)
    if cursor < duration_s:
        keep.append((cursor, duration_s))
    return [(s, e) for s, e in keep if e - s > 0.01]

def to_ffmpeg_select_expr(keep):
    return "+".join(f"between(t,{s:.3f},{e:.3f})" for s, e in keep)

if __name__ == "__main__":
    cuts = json.load(open(sys.argv[1]))
    duration = float(sys.argv[2])
    keep = build_keep_segments(cuts, duration)
    if not keep:
        sys.exit("ERROR: approved cuts cover the entire video duration -- nothing would remain. Check your cuts/duration input.")
    total_cut = duration - sum(e - s for s, e in keep)
    print(f"{len(keep)} keep segments, cutting {total_cut:.1f}s total")
    json.dump(keep, open(sys.argv[3], "w"))
    print("\nffmpeg select/aselect expression:")
    print(to_ffmpeg_select_expr(keep))
