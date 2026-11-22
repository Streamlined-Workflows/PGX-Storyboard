"""Full Assist: turn a song analysis into segments and a story concept.

Cut points are computed here from the beat grid and the lyric timing, so every segment is 5-15 s
and lands on a bar line. The language model (Ollama) names the segments, may merge neighbours that
belong together, and writes the story.
"""
import json
import os
import urllib.error
import urllib.request

OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
MODEL = os.environ.get("OLLAMA_MODEL", "qwen3.6:35b")
MIN_LEN, MAX_LEN, IDEAL_LEN = 5.0, 15.0, 9.0


# ---------- language model ----------

def chat(system, user, schema, think=True, temperature=0.7, timeout=420):
    """Ask the local model for JSON matching `schema`. Raises ValueError with a readable message."""
    payload = {"model": MODEL, "stream": False, "think": think, "format": schema, "keep_alive": "5m",
               "options": {"temperature": temperature, "num_ctx": 16384},
               "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    req = urllib.request.Request(OLLAMA + "/api/chat", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            reply = json.loads(r.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise ValueError(f"The language model returned an error ({e.code}): {detail}")
    except OSError as e:
        raise ValueError(f"Cannot reach the language model (Ollama) at {OLLAMA}: {e}")
    content = (reply.get("message") or {}).get("content", "")
    try:
        return json.loads(content)
    except ValueError:
        raise ValueError("The language model's reply was not usable. Try again.")


def unload():
    """Free the model's memory before a render. Best effort."""
    try:
        req = urllib.request.Request(OLLAMA + "/api/generate", data=json.dumps({"model": MODEL, "keep_alive": 0}).encode(),
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5).read()
    except OSError:
        pass


def status():
    try:
        with urllib.request.urlopen(OLLAMA + "/api/tags", timeout=4) as r:
            names = [m.get("name", "") for m in json.loads(r.read()).get("models", [])]
        return {"ok": True, "model": MODEL, "installed": any(n == MODEL or n.startswith(MODEL + ":") or MODEL.startswith(n) for n in names)}
    except (OSError, ValueError) as e:
        return {"ok": False, "model": MODEL, "error": str(e)}


# ---------- cut points ----------

def _overlap(a0, a1, b0, b1):
    return max(0.0, min(a1, b1) - max(a0, b0))


def lyrics_between(lines, start, end):
    return " / ".join(l["text"] for l in lines if _overlap(l["start"], l["end"], start, end) > 0.4 * min(1.5, l["end"] - l["start"]))


def propose_cuts(analysis, lines):
    """Choose bar-line cut points so every segment is 5-15 s, favouring section changes and lyric phrase starts."""
    duration = float(analysis["duration"])
    bars = [t for t in analysis.get("downbeats") or analysis.get("beats") or [] if 0.5 < t < duration - 0.5]
    if len(bars) < 2:                                    # no usable beat grid: fall back to an even grid
        bars = [i * 2.0 for i in range(1, int(duration // 2))]
    points = [0.0] + sorted(set(round(t, 3) for t in bars)) + [duration]
    section_edges = [s["start"] for s in analysis.get("sections", [])[1:]]

    def boundary_score(t):
        score = 0.0
        if any(abs(t - e) <= 1.2 for e in section_edges):
            score += 3.0
        if any(abs(t - l["start"]) <= 0.45 for l in lines):
            score += 2.0
        if any(l["start"] + 0.35 < t < l["end"] - 0.35 for l in lines):
            score -= 3.0                                 # would cut through a sung line
        return score

    n = len(points)
    best = [float("-inf")] * n
    back = [-1] * n
    best[0] = 0.0
    for j in range(1, n):
        last = j == n - 1
        for i in range(j - 1, -1, -1):
            length = points[j] - points[i]
            if length > MAX_LEN:
                break
            if length < (3.0 if last else MIN_LEN) or best[i] == float("-inf"):
                continue
            score = best[i] + (0.0 if last else boundary_score(points[j])) - 0.15 * abs(length - IDEAL_LEN)
            if score > best[j]:
                best[j], back[j] = score, i
    if best[-1] == float("-inf"):                        # no legal path: even split
        count = max(1, round(duration / IDEAL_LEN))
        cuts = [duration * k / count for k in range(count + 1)]
    else:
        cuts, j = [], n - 1
        while j != -1:
            cuts.append(points[j])
            j = back[j]
        cuts.reverse()

    segments = []
    for start, end in zip(cuts[:-1], cuts[1:]):
        sung = sum(_overlap(l["start"], l["end"], start, end) for l in lines)
        segments.append({"start": round(start, 2), "end": round(end, 2),
                         "type": "singing" if sung >= 0.35 * (end - start) else "story",
                         "lyrics": lyrics_between(lines, start, end)})
    if len(segments) > 1 and segments[-1]["end"] - segments[-1]["start"] < MIN_LEN:      # fold a short tail in
        tail = segments.pop()
        if tail["end"] - segments[-1]["start"] <= MAX_LEN:
            segments[-1]["end"] = tail["end"]
            segments[-1]["lyrics"] = lyrics_between(lines, segments[-1]["start"], tail["end"])
        else:
            segments.append(tail)
    return segments


def describe_song(analysis, lines):
    sections = ", ".join(f'{s["start"]:.0f}-{s["end"]:.0f}s energy {s["energy"]:.2f}' for s in analysis.get("sections", []))
    return f'Length {analysis["duration"]:.0f} s, tempo about {analysis.get("tempo", 0):.0f} BPM. Musical sections: {sections or "not detected"}.'


def name_and_merge(analysis, lines, segments):
    """Let the model name each segment and merge neighbours that share one thought. Code enforces the limits."""
    listing = "\n".join(f'{i}: {s["start"]:.1f}-{s["end"]:.1f}s ({s["end"] - s["start"]:.1f}s) {s["type"]} | lyrics: {s["lyrics"] or "(instrumental)"}'
                        for i, s in enumerate(segments))
    schema = {"type": "object", "required": ["names", "merge_after"], "properties": {
        "names": {"type": "array", "items": {"type": "string"}},
        "merge_after": {"type": "array", "items": {"type": "integer"}}}}
    system = ("You are a music video editor planning shots for a song. You are given segments that were cut on bar lines. "
              "Return JSON only. 'names' must have exactly one short name (2 to 4 words) per segment, in order, such as "
              "'Intro', 'Verse 1 opens', 'Chorus hits', 'Bridge breakdown', 'Final chorus', 'Outro'. "
              "'merge_after' lists segment numbers that should be joined with the segment after them because one lyric "
              "phrase or one musical idea runs across both. Only merge when the joined length stays at or under 15 seconds. "
              "Merging is optional; return an empty list if the cuts already work.")
    try:
        out = chat(system, describe_song(analysis, lines) + "\n\nSegments:\n" + listing, schema, think=False, temperature=0.3)
    except ValueError:
        out = {}
    merged = [dict(s) for s in segments]
    for i in sorted({m for m in out.get("merge_after", []) if isinstance(m, int)}, reverse=True):
        if 0 <= i < len(merged) - 1 and merged[i + 1]["end"] - merged[i]["start"] <= MAX_LEN:
            merged[i]["end"] = merged[i + 1]["end"]
            merged[i]["lyrics"] = lyrics_between(lines, merged[i]["start"], merged[i]["end"])
            sung = sum(_overlap(l["start"], l["end"], merged[i]["start"], merged[i]["end"]) for l in lines)
            merged[i]["type"] = "singing" if sung >= 0.35 * (merged[i]["end"] - merged[i]["start"]) else "story"
            merged[i]["_merged"] = True
            del merged[i + 1]
    names = out.get("names") or []
    use_names = len(names) == len(segments) and not any(s.get("_merged") for s in merged)
    for i, s in enumerate(merged):
        s.pop("_merged", None)
        s["name"] = (str(names[i]).strip()[:40] if use_names and str(names[i]).strip() else f"Segment {i + 1}")
    if not use_names and names:                           # merges shifted the numbering: name again, quickly
        try:
            listing = "\n".join(f'{i}: {s["start"]:.1f}-{s["end"]:.1f}s {s["type"]} | lyrics: {s["lyrics"] or "(instrumental)"}' for i, s in enumerate(merged))
            again = chat("Name each music video segment in 2 to 4 words. Return JSON with 'names', exactly one per segment, in order.",
                         listing, {"type": "object", "required": ["names"], "properties": {"names": {"type": "array", "items": {"type": "string"}}}},
                         think=False, temperature=0.3)
            if len(again.get("names", [])) == len(merged):
                for s, name in zip(merged, again["names"]):
                    s["name"] = str(name).strip()[:40] or s["name"]
        except ValueError:
            pass
    return merged


# ---------- lyrics ----------

def align_lyrics(lines, pasted):
    """Replace the transcribed words with the user's real lyrics, keeping the transcribed timing."""
    listing = "\n".join(f'{i}: {l["start"]:.2f}-{l["end"]:.2f} | {l["text"]}' for i, l in enumerate(lines))
    schema = {"type": "object", "required": ["lines"], "properties": {"lines": {"type": "array", "items": {
        "type": "object", "required": ["start", "end", "text"],
        "properties": {"start": {"type": "number"}, "end": {"type": "number"}, "text": {"type": "string"}}}}}}
    system = ("You align song lyrics to timing. You get a rough machine transcription with start and end times in seconds, "
              "and the correct lyrics as text. Return JSON 'lines': the correct lyrics split into sung lines, each with the "
              "start and end time of the transcribed line or lines it corresponds to. Keep times in order and inside the "
              "transcription's range. Use only words from the correct lyrics. Skip section labels such as [Chorus]. "
              "If part of the correct lyrics has no matching transcription, estimate its time from its neighbours.")
    out = chat(system, "Transcription:\n" + listing + "\n\nCorrect lyrics:\n" + pasted.strip()[:6000], schema, think=True, temperature=0.2)
    fixed, last = [], 0.0
    for line in out.get("lines", []):
        try:
            start, end, text = float(line["start"]), float(line["end"]), str(line["text"]).strip()
        except (KeyError, TypeError, ValueError):
            continue
        if not text or end <= start:
            continue
        start = max(start, last)
        if end - start < 0.2:
            continue
        fixed.append({"start": round(start, 2), "end": round(end, 2), "text": text[:300]})
        last = start
    if len(fixed) < max(1, len(lines) // 3):
        raise ValueError("The model could not match those lyrics to the timing. The transcribed lines were kept.")
    return fixed


# ---------- story ----------

def write_story(analysis, lines, segments, direction="", style="", previous=None):
    listing = "\n".join(f'{i + 1}. "{s.get("name") or "Segment"}" {s["start"]:.1f}-{s["end"]:.1f}s, {s.get("type", "story")} shot | lyrics: '
                        f'{lyrics_between(lines, s["start"], s["end"]) or "(instrumental)"}' for i, s in enumerate(segments))
    schema = {"type": "object", "required": ["title", "logline", "style", "beats"], "properties": {
        "title": {"type": "string"}, "logline": {"type": "string"}, "style": {"type": "string"},
        "beats": {"type": "array", "items": {"type": "string"}}}}
    system = ("You are a music video director writing a rough story concept for a song. Return JSON only. "
              "'title': a working title. 'logline': two or three sentences that pitch the video's story and emotional arc. "
              "'style': one sentence on the visual look. 'beats': exactly one entry per segment, in order; each is one or "
              "two plain sentences saying what we see in that segment, driven by that segment's lyrics and energy and by "
              "where it sits in the story. Singing shots show the performer singing; story shots carry the plot. Build to "
              "the loudest sections and give the ending a clear final image. Keep recurring characters and places "
              "consistent from segment to segment. Describe only what a camera can see.")
    user = describe_song(analysis, lines) + f"\n\nSegments ({len(segments)}):\n" + listing
    if style.strip():
        user += "\n\nVisual style wanted: " + style.strip()[:400]
    if direction.strip():
        user += "\n\nDirection from the artist: " + direction.strip()[:800]
    if previous:
        user += "\n\nThe artist rejected this earlier concept, so write a clearly different one: " + str(previous)[:600]
    out = chat(system, user, schema, think=True, temperature=0.9)
    beats = [str(b).strip() for b in out.get("beats", [])]
    if len(beats) != len(segments):
        beats = (beats + [""] * len(segments))[:len(segments)]
    return {"title": str(out.get("title", "")).strip()[:120], "logline": str(out.get("logline", "")).strip(),
            "style": str(out.get("style", "")).strip(), "beats": beats, "direction": direction, "style_note": style}
