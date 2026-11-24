"""Assisted Storyboard: turn a song analysis into segments and a story concept.

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

before_chat = None      # set by the server: makes room for the language model before it is asked to work
active = 0              # how many requests the language model is working on right now; it is never unloaded mid-answer
_active_lock = __import__("threading").Lock()


def chat(system, user, schema, think=True, temperature=0.7, timeout=420, images=None, ctx=16384):
    if before_chat:
        try:
            before_chat()
        except Exception:
            pass                                   # making room is a courtesy; the request goes ahead regardless
    global active
    with _active_lock:
        active += 1
    try:
        return _chat_with_retry(system, user, schema, think, temperature, timeout, images, ctx)
    finally:
        with _active_lock:
            active -= 1


def _chat_with_retry(system, user, schema, think=True, temperature=0.7, timeout=420, images=None, ctx=16384):
    """Ask the local model for JSON matching `schema`; see _chat. If the reply is cut off or empty (usually because
    its private reasoning used up the room), ask once more without the reasoning step and with more room."""
    try:
        return _chat(system, user, schema, think, temperature, timeout, images, ctx)
    except IncompleteReply:
        try:
            return _chat(system, user, schema, False, temperature, timeout, images, max(ctx, 32768))
        except IncompleteReply as e:
            raise ValueError(str(e))


class IncompleteReply(ValueError):
    pass


def _chat(system, user, schema, think, temperature, timeout, images, ctx):
    """Ask the local model for JSON matching `schema`. Raises ValueError with a readable message.

    `images` is an optional list of base64-encoded images for the model to look at.
    """
    message = {"role": "user", "content": user}
    if images:
        message["images"] = images
    payload = {"model": MODEL, "stream": False, "think": think, "format": schema, "keep_alive": "5m",
               "options": {"temperature": temperature, "num_ctx": ctx, "num_predict": -1},
               "messages": [{"role": "system", "content": system}, message]}
    req = urllib.request.Request(OLLAMA + "/api/chat", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            reply = json.loads(r.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        if images and ("image" in detail.lower() or "vision" in detail.lower() or "multimodal" in detail.lower()):
            raise ValueError(f"The language model ({MODEL}) cannot look at images: {detail}")
        raise ValueError(f"The language model returned an error ({e.code}): {detail}")
    except OSError as e:
        raise ValueError(f"Cannot reach the language model (Ollama) at {OLLAMA}: {e}")
    content = (reply.get("message") or {}).get("content", "")
    try:
        return json.loads(content)
    except ValueError:
        why = ("it ran out of room before finishing" if reply.get("done_reason") == "length" else
               "it returned nothing" if not content.strip() else "its answer was not complete")
        raise IncompleteReply(f"The language model's reply was not usable: {why} "
                              f"({reply.get('prompt_eval_count', '?')} tokens in, {reply.get('eval_count', '?')} out, "
                              f"stopped: {reply.get('done_reason', '?')}). Try again.")


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

def with_lore(user, lore):
    """Add the artist's background notes to a request. They inform the answer; they are not a list of things to show."""
    if not (lore or "").strip():
        return user
    return (user + "\n\nSetting and lore for this video, written by the artist. Stay consistent with it: use its names, places, "
            "factions, technology and look where the story touches them, and do not contradict it. Do not try to show all of it.\n" + lore.strip())


def write_story(analysis, lines, segments, direction="", style="", previous=None, lore="", keep=None, guidance=""):
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
    if guidance.strip():                              # the kind of video, from the project's configuration
        user += "\n\nKind of video: " + guidance.strip()
    if style.strip():
        user += "\n\nVisual style wanted: " + style.strip()[:400]
    if direction.strip():
        user += "\n\nDirection from the artist: " + direction.strip()[:800]
    if previous:
        user += "\n\nThe artist rejected this earlier concept, so write a clearly different one: " + str(previous)[:600]
    keep = {i: t for i, t in (keep or {}).items() if 0 <= i < len(segments) and str(t).strip()}
    if keep:                                          # beats the artist locked: the new story has to pass through them
        user += ("\n\nThe artist has locked what we see in these segments. Keep each exactly as written and build the rest of the "
                 "story so it leads into and out of them:\n" + "\n".join(f"{i + 1}. {t}" for i, t in sorted(keep.items())))
    user = with_lore(user, lore)
    out = chat(system, user, schema, think=True, temperature=0.9, ctx=32768 if lore else 16384)
    beats = [str(b).strip() for b in out.get("beats", [])]
    if len(beats) != len(segments):
        beats = (beats + [""] * len(segments))[:len(segments)]
    for i, t in keep.items():                         # whatever the model returned, a locked beat stays word for word
        beats[i] = str(t).strip()
    return {"title": str(out.get("title", "")).strip()[:120], "logline": str(out.get("logline", "")).strip(),
            "style": str(out.get("style", "")).strip(), "beats": beats, "direction": direction, "style_note": style}


# ---------- actors ----------

VIEW_FRAMINGS = [
    ("close-up", "Close-up portrait, head and shoulders, facing the camera with a calm, neutral expression"),
    ("waist up", "Medium shot from the waist up, three-quarter view, relaxed natural pose"),
    ("full body", "Full-body shot, standing, the whole figure visible from head to feet"),
    # asked for one at a time with "Generate specific view"
    ("3/4 left", "Medium shot from the waist up, body and face turned three-quarters toward the left side of the frame"),
    ("3/4 right", "Medium shot from the waist up, body and face turned three-quarters toward the right side of the frame"),
    ("left", "Medium shot from the waist up in strict side profile, facing the left edge of the frame"),
    ("right", "Medium shot from the waist up in strict side profile, facing the right edge of the frame"),
    ("rear", "Medium shot from the waist up seen from directly behind, back to the camera, face not visible"),
]
STANDARD_VIEWS = ("close-up", "waist up", "full body")


REFERENCE_LIMIT = 300                # characters a described reference may add to a prompt, label included
REFERENCE_ASKS = {
    "style guide": ("Visual style: ",
                    "You are shown one picture. Describe ONLY its visual style so an image generator can match the look on a "
                    "different subject: colour palette, materials and surface finish, lighting, and rendering style. Do not say what "
                    "the picture shows. Do not mention the subject, its shape, its parts, its layout, how many of anything there "
                    "are, or the background. Return JSON with 'description': one or two plain sentences, at most 250 characters, "
                    "with no preamble and no line breaks."),
    "inspiration": ("Loosely inspired by: ",
                    "You are shown one picture. Describe in general terms the idea it conveys, as loose inspiration for an image "
                    "generator: what kind of thing it is, its overall shape language and its mood. Stay general. Leave out exact "
                    "details, counts, colours, text, the background and the camera angle. Return JSON with 'description': one or "
                    "two plain sentences, at most 250 characters, with no preamble and no line breaks."),
}


def describe_reference(image_b64, use):
    """Turn a reference picture into words for the prompt, so the picture itself need not be sent to the image model.
    `use` is "style guide" (its look only) or "inspiration" (its general idea). -> text of at most REFERENCE_LIMIT characters,
    starting with a label that says what it is."""
    if use not in REFERENCE_ASKS:
        raise ValueError("Only a style guide or an inspiration reference is described in words.")
    label, system = REFERENCE_ASKS[use]
    schema = {"type": "object", "required": ["description"], "properties": {"description": {"type": "string"}}}
    out = chat(system, "Describe this picture as instructed.", schema, think=False, temperature=0.3, images=[image_b64])
    text = _fit(out.get("description", ""), REFERENCE_LIMIT - len(label))
    if not text:
        raise ValueError("The language model returned no description. Try again.")
    return label + text


def compare_references(pictures, what, aspects):
    """Compare several views of one subject and report where they disagree. `pictures` is [(name, image_b64)], in order.
    Advice only: the pictures are not changed and nothing is blocked because of what comes back.
    -> [{"views": [name...], "aspect", "description", "certain": bool}]"""
    names = [n for n, _ in pictures]
    system = ("You check reference sheets for 3D artists. You are shown several views of what should be the same subject, in a fixed order. "
              "Report only real disagreements between the views: a feature present in one view and missing or different in another, "
              "a different count of parts, different proportions, colours or materials, a different pose, a view that faces the wrong way "
              "for its name, or more than the one subject in a picture. Do not report things that differ only because the camera moved. "
              "For each finding name the views involved using exactly the names given, choose the one aspect that fits best, describe it in "
              "one or two plain sentences, and set certain to false if you are not sure. If the views agree, return an empty list.")
    schema = {"type": "object", "required": ["findings"], "properties": {"findings": {"type": "array", "items": {
        "type": "object", "required": ["views", "aspect", "description", "certain"],
        "properties": {"views": {"type": "array", "items": {"type": "string", "enum": names}}, "aspect": {"type": "string", "enum": list(aspects)},
                       "description": {"type": "string"}, "certain": {"type": "boolean"}}}}}}
    user = f"The subject: {what}. The pictures, in order: " + ", ".join(f"{i}. {n} view" for i, n in enumerate(names, 1)) + ". List the disagreements."
    out = chat(system, user, schema, think=False, temperature=0.2, images=[b for _, b in pictures])
    return out.get("findings") if isinstance(out.get("findings"), list) else []


def _fit(text, room):
    """Trim to `room` characters at the end of a sentence if one fits, else at a word, and end with a full stop."""
    text = " ".join(str(text).split())
    if len(text) > room:
        cut = text[:room]
        stop = max(cut.rfind(". "), cut.rfind("; "))
        text = cut[:stop + 1] if stop > room * 0.5 else cut[:cut.rfind(" ")].rstrip(",;:") + "."
    return text if not text or text.endswith((".", "!", "?")) else text + "."


def combine_references(text, references=1):
    """Rewrite the collected reference descriptions as one clean passage: overlap removed, wording tidied, every distinct
    point kept, nothing new added. The result may run to REFERENCE_LIMIT characters for each reference it draws on."""
    text = " ".join(str(text or "").split())
    if not text:
        raise ValueError("There is no reference text to clean up. Press Apply on a style guide or inspiration reference first.")
    room = REFERENCE_LIMIT * max(1, min(4, int(references or 1)))
    schema = {"type": "object", "required": ["description"], "properties": {"description": {"type": "string"}}}
    system = ("You are given short notes written for an image generator. They were taken from several reference pictures: some "
              "describe a visual style, some a general idea, and they may repeat or overlap each other. Rewrite them as ONE clean "
              "passage for the image generator. Remove repetition and overlap, reconcile the wording, and keep every distinct point. "
              "Add nothing that is not in the notes, and do not describe a subject the notes do not mention. Write plain sentences "
              f"with no labels, no list and no line breaks. Return JSON with 'description', at most {room - 20} characters.")
    out = chat(system, "Notes:\n" + text[:4 * REFERENCE_LIMIT + 400], schema, think=False, temperature=0.3)
    result = _fit(out.get("description", ""), room)
    if not result:
        raise ValueError("The language model returned nothing. Try again.")
    return result


def describe_actor(name, images_b64):
    """Look at an actor's views and write the description used to generate more images of them."""
    schema = {"type": "object", "required": ["description"], "properties": {"description": {"type": "string"}}}
    system = ("You write character descriptions for an image generator. You are shown one or more pictures of the same "
              "character. Return JSON with 'description': three or four sentences that would let an artist redraw this "
              "character consistently. Start with the art style (for example 'Stylized 3D animated film character' or "
              "'Photorealistic'). Then cover apparent age range, build, hair colour and style, face and eyes, clothing with "
              "colours and materials, and any distinguishing details. Describe only the character: leave out the background, "
              "the pose, the lighting and the camera. Do not give them a name and do not guess who they are.")
    out = chat(system, f"Describe this character{(' (the artist calls them ' + name + ')') if name else ''}.", schema,
               think=False, temperature=0.3, images=images_b64)
    text = str(out.get("description", "")).strip()
    if not text:
        raise ValueError("The language model did not return a description. Try again.")
    return text[:1200]


def view_prompt(description, framing, has_refs, extra=""):
    """`extra` is a one-off addition for this generation (a prop, a change of outfit or hair).

    The addition is stated first and the reference is then limited to face, build and hair colour. Telling the model to
    "keep the hair exactly" as well made it copy the reference's loose hair straight through a helmet.
    """
    who = (description or "").strip().rstrip(".")
    extra = (extra or "").strip().rstrip(".")
    keep = "face and build exactly, and the same hair colour" if extra else "face, hair and build exactly"
    if has_refs and who:      # the written description is the authority on clothing and colours, so an actor can be re-dressed
        lead = (f"The same person as in the reference image: keep their {keep}. "
                f"Their clothing and its colours follow this description, even where the reference image differs: {who}")
    elif has_refs:
        lead = f"The same character as in the reference image: keep their {keep}"
    else:
        lead = who
    if extra:
        change = (f"In this picture: {extra}. This is the most important instruction: how the hair is arranged and what is worn "
                  "follow it, not the " + ("reference image" if has_refs else "description") + " where they differ")
        lead = change + ". " + lead if lead else change
    return (f"{framing}. {lead}. Plain dark studio backdrop, soft cinematic lighting, sharp focus, "
            "consistent character design, single character, no text.")


# ---------- cast and shots ----------

def energy_word(analysis, start, end):
    total = weight = 0.0
    for sec in analysis.get("sections", []):
        o = _overlap(sec["start"], sec["end"], start, end)
        total, weight = total + o * sec.get("energy", 0), weight + o
    e = total / weight if weight else 0.5
    return "quiet" if e < 0.35 else "mid energy" if e < 0.65 else "loud"


# ---------- scene assets, world assets and props ----------

# What to draw for each kind when its pictures are generated: (label, framing).
THING_VIEWS = {
    "scene": [("establishing", "Wide establishing shot showing the whole of it in its setting"),
              ("three-quarter", "Three-quarter view of the whole of it, clearly lit, filling most of the frame"),
              ("detail", "Close view of its most distinctive detail")],
    "prop": [("main", "The whole object in a three-quarter view on a plain neutral studio background, evenly lit"),
             ("side", "The whole object in a straight side view on a plain neutral studio background"),
             ("in use", "The object in use, held or operated, hands only, no face")],
}
THING_VIEWS["world"] = THING_VIEWS["scene"]
THING_WORDS = {"scene": "scene asset", "world": "world asset", "prop": "prop"}


def thing_prompt(thing, framing, has_refs, extra=""):
    """The FLUX.2 prompt for one picture of a scene asset, world asset or prop."""
    name, context = (thing.get("name") or "the subject").strip(), (thing.get("context") or "").strip().rstrip(".")
    parts = []
    if extra.strip():
        parts.append(f"For this picture: {extra.strip().rstrip('.')}.")
    parts.append(f"{framing} of {name}." + (f" {context}." if context else ""))
    if (thing.get("description") or "").strip():
        parts.append(thing["description"].strip().rstrip(".") + ".")
    if has_refs:
        parts.append("It is the same one shown in the reference images: keep its shape, proportions, colours and markings exactly.")
    parts.append("No people unless stated. Cinematic, sharp focus, no text, no watermark.")
    return " ".join(parts)


def story_listing(story, analysis, lines, segments):
    beats = dict(zip(story.get("segment_ids", []), story.get("beats", [])))
    tempo = analysis.get("tempo") or 0
    out = []
    for i, s in enumerate(segments):
        bars = f", about {round((s['end'] - s['start']) * tempo / 240)} bars" if tempo else ""
        out.append(f'{i + 1}. "{s.get("name") or "Segment"}" {s["start"]:.1f}-{s["end"]:.1f}s{bars}, {energy_word(analysis, s["start"], s["end"])}, '
                   f'{s.get("type", "story")} shot | lyrics: {lyrics_between(lines, s["start"], s["end"]) or "(instrumental)"} | '
                   f'story beat: {beats.get(s["id"]) or s.get("prompt") or "(none)"}')
    return "\n".join(out)


def story_header(story):
    return f'Title: {story.get("title", "")}\nStory: {story.get("logline", "")}\nVisual style: {story.get("style", "")}'


def recommend_cast(story, analysis, lines, segments, existing, lore=""):
    schema = {"type": "object", "required": ["characters"], "properties": {"characters": {"type": "array", "items": {
        "type": "object", "required": ["name", "role", "description"], "properties": {
            "name": {"type": "string"}, "role": {"type": "string"}, "description": {"type": "string"}}}}}}
    system = ("You are casting a music video from its story concept. Return JSON only. List the characters the story needs, "
              "most important first: at least 1, at most 4, and only characters who are actually seen. For each: 'name' is a short "
              "name to call them; 'role' is one sentence on who they are in the story and whether they are the one singing; "
              "'description' is two or three sentences an illustrator can draw from: age, build, hair, face, clothing and one "
              "distinctive detail, in the video's visual style. Describe appearance only, no backstory.")
    user = story_header(story) + "\n\nSegments:\n" + story_listing(story, analysis, lines, segments)
    if existing:
        user += "\n\nThe artist already has these actors, so do not repeat them: " + ", ".join(existing)
    user = with_lore(user, lore)
    out = chat(system, user, schema, think=True, temperature=0.8, ctx=32768 if lore else 16384)
    return [{"name": str(c.get("name", "")).strip()[:40], "role": str(c.get("role", "")).strip()[:300],
             "description": str(c.get("description", "")).strip()[:900]} for c in out.get("characters", [])[:4] if str(c.get("name", "")).strip()]


def write_shots(story, analysis, lines, segments, cast, lore="", things=(), guidance=""):
    """Plan the key frames, and decide for each segment whether it continues the previous shot or cuts to a new scene."""
    frame = {"type": "object", "required": ["description", "cast", "assets"], "properties": {
        "description": {"type": "string"}, "cast": {"type": "array", "items": {"type": "string"}},
        "assets": {"type": "array", "items": {"type": "string"}}}}
    schema = {"type": "object", "required": ["first_frame", "segments"], "properties": {"first_frame": frame, "segments": {"type": "array", "items": {
        "type": "object", "required": ["starts", "reason", "begin_frame", "end_frame"], "properties": {
            "starts": {"type": "string", "enum": ["continue", "new_scene"]}, "reason": {"type": "string"},
            "begin_frame": frame, "end_frame": frame}}}}}
    names = [c["name"] for c in cast]
    system = ("You are a music video director planning key frames. Each segment of the video is generated by a video model that "
              "starts on one still image and moves toward another. Return JSON only. 'first_frame' is the still the video opens on. "
              "'segments' has exactly one entry per segment, in order.\n"
              "For each segment first decide 'starts'. Use 'continue' when the segment carries on the same shot as the one before: "
              "same place, same subject, the action simply flows on, so it should begin on the exact frame the previous segment "
              "ended on. Use 'new_scene' when the segment should cut: the place changes, the subject changes (for example from "
              "someone singing inside a cockpit to the ship seen from outside as it starts to move), time jumps, the lyrics or "
              "story beat turn to something that cannot be shown from the previous shot, or the music changes section sharply "
              "and a cut would land on it. A singing shot that follows a story shot of something else, and a story shot that "
              "leaves the singer, are new scenes. Do not cut inside one continuous action, and do not stay on one shot for more "
              "than about three segments in a row. Segment 1 is always 'new_scene'. 'reason' is one short sentence saying why.\n"
              "'begin_frame': for a new scene, the still that the segment opens on; for 'continue' leave its description empty. "
              "'end_frame': the still the segment ends on, decided from that segment's lyrics, energy and length, its story beat "
              "and where it sits in the story, so that going from where the segment starts to this frame is the action of the "
              "segment and fits in its few seconds.\n"
              "Each 'description' is two or three sentences describing one frozen image: who is in frame, their pose and "
              "expression, the framing (close-up, medium, wide), the place and the light. Keep places, props and clothing "
              "consistent unless the story changes them. In a singing shot the performer faces the camera, mouth open mid-line. "
              "Describe only what is visible; no camera moves, no sound, no text on screen. 'cast' lists which of the named cast "
              "members are visible in that frame, using their names exactly as given, or an empty list. 'assets' lists which of the "
              "named assets and props are visible in that frame, using their names exactly as given, or an empty list. Use the "
              "listed assets and props wherever the story calls for such a thing, in place of inventing a new one; many frames "
              "will use none.")
    people = "\n".join(f'- {c["name"]}: {c.get("role") or "cast member"}. Looks: {c.get("description") or "not described"}' for c in cast)
    user = (story_header(story) + "\n\nCast:\n" + (people or "(none chosen: describe the people the story needs)") +
            f"\n\nSegments ({len(segments)}):\n" + story_listing(story, analysis, lines, segments))
    if things:                                        # names and one line of context only; their pictures do the describing later
        user += "\n\nAssets and props available:\n" + "\n".join(
            f'- {t["name"]} ({THING_WORDS.get(t.get("kind"), "asset")})' + (f': {t["context"]}' if t.get("context") else "") for t in things)
    if guidance.strip():                              # how much to say about each frame, from the project's configuration
        user += "\n\nLevel of detail wanted: " + guidance.strip()
    user = with_lore(user, lore)
    out = chat(system, user, schema, think=True, temperature=0.7, timeout=900, ctx=32768)     # one long answer: a frame or two per segment

    def clean(f):
        f = f if isinstance(f, dict) else {}
        lowered = {n.lower(): n for n in names}
        who = [lowered[str(w).strip().lower()] for w in f.get("cast", []) if str(w).strip().lower() in lowered]
        known = {t["name"].lower(): t["name"] for t in things}
        what = [known[str(w).strip().lower()] for w in f.get("assets", []) if str(w).strip().lower() in known]
        return {"text": str(f.get("description", "")).strip(), "who": list(dict.fromkeys(who)), "what": list(dict.fromkeys(what))}
    first = clean(out.get("first_frame"))
    ends = []
    for i in range(len(segments)):
        item = (out.get("segments") or [])[i] if i < len(out.get("segments") or []) else {}
        item = item if isinstance(item, dict) else {}
        begin = clean(item.get("begin_frame"))
        new = i == 0 or (item.get("starts") == "new_scene" and bool(begin["text"]))     # a cut needs a frame to cut to
        ends.append({**clean(item.get("end_frame")), "start": "new" if new else "continue",
                     "reason": str(item.get("reason", "")).strip()[:240], "begin": first if i == 0 else begin})
    return {"first": first, "ends": ends}


def shot_prompt(text, style, people, things=(), described=()):
    """The FLUX.2 prompt for one key frame. `people` are the cast members whose reference pictures are attached, in order;
    `things` are assets and props whose pictures follow them; `described` are ones in frame with no picture attached."""
    parts = [text.strip().rstrip(".") + "."]
    for i, c in enumerate(people):
        look = (c.get("description") or "").strip().rstrip(".")
        parts.append(f'{c["name"]} is the character in reference image {i + 1}; keep their face, hair and build exactly' +
                     (f". Their clothing and its colours follow this description: {look}." if look else ", and their outfit as shown."))
    for i, t in enumerate(things, len(people) + 1):
        parts.append(f'{t["name"]} is the {"object" if t.get("kind") == "prop" else "subject"} shown in reference image {i}; keep its shape, proportions, colours and markings exactly.')
    for t in described:
        look = ". ".join(x.strip().rstrip(".") for x in (t.get("context") or "", t.get("description") or "") if x.strip())
        if look:
            parts.append(f'{t["name"]}: {look}.')
    if style.strip():
        parts.append("Visual style: " + style.strip().rstrip(".") + ".")
    parts.append("Cinematic widescreen film still, sharp focus, no text, no watermark.")
    return " ".join(parts)
