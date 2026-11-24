"""Turning a timeline into finished audio.

The timeline is a set of instructions; this module carries them out with ffmpeg and writes a new
file. Original sounds are only ever read.

Everything is placed by whole samples at the timeline's own rate, so a clip that starts at sample
N on the timeline starts at sample N in the export, and the same timeline always gives the same
result. The export is only resampled, if a different rate was asked for, at the very end.

Order of work for each clip:   cut out the part used -> reverse -> speed and pitch -> gain -> fades
                               -> the clip's effects -> placed on the timeline
for each track:                its clips added together -> the track's effects -> volume -> balance
for the mix:                   the tracks added together -> master effects -> master volume

Nothing is normalised or limited on the way out. The loudest point is measured and reported, so a
mix that would clip is flagged instead of being silently changed.
"""
import array
import math
import os
import random
import re
import shutil
import subprocess
import sys
import wave

from . import schemas

OUT_RATES = (44100, 48000)
OUT_FORMATS = {"wav": ("audio/wav", (16, 24)), "flac": ("audio/flac", (16, 24)), "mp3": ("audio/mpeg", ())}
MP3_RATES = (128, 192, 256, 320)
SEEKABLE = ("wav", "flac")          # formats ffmpeg can jump into at an exact sample; others are read from their start
PREDELAY = 0.04                     # seconds of gap before the reverb at size 1

_features = {}


def features():
    """What this machine's ffmpeg understands. Checked once."""
    if not _features:
        version = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=30).stdout
        found = re.search(r"ffmpeg version n?(\d+)\.", version)
        afir = subprocess.run(["ffmpeg", "-hide_banner", "-h", "filter=afir"], capture_output=True, text=True, timeout=30).stdout
        _features.update(major=int(found.group(1)) if found else 6, irnorm=bool(re.search(r"^\s+irnorm\s", afir, re.M)),
                         mp3="libmp3lame" in subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=30).stdout)
    return _features


# ---------- the reverb's impulse response ----------

def impulse(folder, size, decay_s, rate):
    """-> the path of a WAV holding the room sound for these settings: noise that dies away over decay_s, after a
    short gap set by size. Made from a fixed seed, so it is the same on every machine, and kept once made. The
    browser's preview loads the same file, so preview and export use one room."""
    size, decay_s = min(1.0, max(0.0, round(float(size), 2))), min(10.0, max(0.1, round(float(decay_s), 1)))
    path = os.path.join(folder, f"room-{rate}-{int(round(size * 100)):03d}-{int(round(decay_s * 10)):03d}.wav")
    if os.path.isfile(path):
        return path
    os.makedirs(folder, exist_ok=True)
    gap, body = int(size * PREDELAY * rate), int(decay_s * rate)
    smooth = 0.35 + 0.5 * size                                   # larger rooms sound darker
    channels = []
    for seed in (1811, 2903):
        rng, last, energy, data = random.Random(seed), 0.0, 0.0, array.array("f", bytes(4 * gap))
        for i in range(body):
            last = smooth * last + (1 - smooth) * rng.uniform(-1, 1)
            value = last * math.exp(-6.908 * i / body)           # 60 dB quieter by the end
            energy += value * value
            data.append(value)
        scale = 1 / math.sqrt(energy)                            # the room neither adds nor takes away loudness on average
        channels.append(array.array("f", (v * scale for v in data)))
    mixed = array.array("f", bytes(8 * len(channels[0])))
    mixed[0::2], mixed[1::2] = channels[0], channels[1]
    if sys.byteorder == "big":
        mixed.byteswap()
    body_bytes = mixed.tobytes()
    header = (b"RIFF" + (36 + len(body_bytes)).to_bytes(4, "little") + b"WAVEfmt " + (16).to_bytes(4, "little") + (3).to_bytes(2, "little")
              + (2).to_bytes(2, "little") + rate.to_bytes(4, "little") + (rate * 8).to_bytes(4, "little") + (8).to_bytes(2, "little")
              + (32).to_bytes(2, "little") + b"data" + len(body_bytes).to_bytes(4, "little"))
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "wb") as f:
        f.write(header + body_bytes)
    os.replace(tmp, path)
    return path


def tail_of(effect):
    """How long a reverb keeps ringing after its input stops, in seconds. Zero for anything else."""
    p = effect["params"]
    return p["decay_s"] + p["size"] * PREDELAY if effect["type"] == "reverb" and effect["on"] and p["mix"] > 0 else 0.0


# ---------- the filter graph ----------

class _Graph:
    def __init__(self, rate, room):
        self.rate, self.room = rate, room            # room(size, decay_s) -> path of the impulse file
        self.inputs, self.lines, self.n = [], [], 0

    def label(self):
        self.n += 1
        return f"s{self.n}"

    def source(self, path, seek=0):
        self.inputs.append((path, seek))
        return f"{len(self.inputs) - 1}:a"

    def run(self, sources, filters, outputs=1):
        """Add one chain: [sources] filter,filter,… [outputs]. -> the new label, or a list of them."""
        made = [self.label() for _ in range(outputs)]
        self.lines.append("".join(f"[{s}]" for s in ([sources] if isinstance(sources, str) else sources)) + ",".join(filters) + "".join(f"[{m}]" for m in made))
        return made[0] if outputs == 1 else made

    def mix(self, labels):
        return labels[0] if len(labels) == 1 else self.run(labels, [f"amix=inputs={len(labels)}:normalize=0:duration=longest"])

    def effects(self, stream, chain):
        for fx in chain:
            if not fx["on"]:
                continue
            p = fx["params"]
            if fx["type"] == "eq":
                bands = ([f"bass=g={p['low_db']}:f={p['low_hz']}:t=s:w=1"] if p["low_db"] else []) \
                      + ([f"equalizer=f={p['mid_hz']}:t=q:w=1:g={p['mid_db']}"] if p["mid_db"] else []) \
                      + ([f"treble=g={p['high_db']}:f={p['high_hz']}:t=s:w=1"] if p["high_db"] else [])
                if bands:
                    stream = self.run(stream, bands)
            elif fx["type"] == "compressor":
                stream = self.run(stream, [f"acompressor=threshold={_gain(p['threshold_db']):.6f}:ratio={p['ratio']}:attack={p['attack_ms']}"
                                           f":release={p['release_ms']}:makeup={_gain(p['makeup_db']):.6f}:knee=2.82843"])
            elif fx["type"] == "reverb" and p["mix"] > 0:
                room = self.source(self.room(p["size"], p["decay_s"]))
                padded = self.run(stream, [f"apad=pad_len={int(round(tail_of(fx) * self.rate))}"])     # room for the reverb to die away
                dry, wet = self.run(padded, ["asplit=2"], 2)
                plain = "irnorm=-1:irlink=0" if features()["irnorm"] else "gtype=none"                 # use the room exactly as made
                shaped = self.run(room, [f"aresample={self.rate}", "aformat=sample_fmts=fltp:channel_layouts=stereo"])
                wet = self.run([wet, shaped], [f"afir=dry=1:wet=1:{plain}", f"volume={p['mix']:.6f}"])
                dry = self.run(dry, [f"volume={1 - p['mix']:.6f}"])
                stream = self.run([dry, wet], ["amix=inputs=2:normalize=0:duration=longest"])
        return stream

    def clip(self, clip, path, fmt, channels=2):
        rate, length = self.rate, clip["length"]
        tone = 2 ** (clip["pitch"] / 12.0)
        used = max(1, int(round(length * clip["speed"])))                  # how much of the sound this clip plays through
        seek = max(0, clip["offset"] // rate - 1) if fmt in SEEKABLE else 0  # skip to a whole second just before; the exact cut is made below
        start = clip["offset"] - seek * rate
        # A one-channel sound plays at its full level on both sides, as it does in the browser.
        both = "pan=stereo|c0=c0|c1=c0" if channels == 1 else "aformat=channel_layouts=stereo"
        steps = [f"aresample={rate}", both, "aformat=sample_fmts=fltp", f"atrim=start_sample={start}:end_sample={start + used}", "asetpts=N/SR/TB"]
        if clip["reverse"]:
            steps.append("areverse")
        if abs(tone - 1) > 1e-9:
            steps += [f"asetrate={rate * tone:.6f}", f"aresample={rate}"]
        tempo = clip["speed"] / tone
        while tempo > 2 + 1e-9:
            steps.append("atempo=2"); tempo /= 2
        while tempo < 0.5 - 1e-9:
            steps.append("atempo=0.5"); tempo /= 0.5
        if abs(tempo - 1) > 1e-9:
            steps.append(f"atempo={tempo:.9f}")
        steps += ["asetpts=N/SR/TB", f"apad=whole_len={length}", f"atrim=end_sample={length}"]      # exactly as long as the clip, whatever the sound gave
        if clip["gain_db"]:
            steps.append(f"volume={_gain(clip['gain_db']):.9f}")
        if clip["fade_in"]:
            steps.append(f"afade=t=in:ss=0:ns={clip['fade_in']}")
        if clip["fade_out"]:
            steps.append(f"afade=t=out:ss={length - clip['fade_out']}:ns={clip['fade_out']}")
        stream = self.effects(self.run(self.source(path, seek), steps), clip["effects"])
        return self.run(stream, [f"adelay=delays={clip['start']}S:all=1"]) if clip["start"] else stream

    def track(self, track, files):
        clips = [self.clip(c, *files[c["asset_id"]]) for c in track["clips"] if not c["muted"] and c["asset_id"] in files]
        if not clips:
            return None
        stream = self.effects(self.mix(clips), track["effects"])
        left, right = 1 - max(0.0, track["pan"]), 1 + min(0.0, track["pan"])      # balance: turning towards one side lowers the other
        steps = ([f"volume={_gain(track['volume_db']):.9f}"] if track["volume_db"] else []) \
              + ([f"pan=stereo|c0={left:.6f}*c0|c1={right:.6f}*c1"] if track["pan"] else [])
        return self.run(stream, steps) if steps else stream


def _gain(db):
    return 10 ** (db / 20.0)


def length_of(timeline, tracks=None, master=True):
    """How long the export runs, in samples at the timeline's rate: to the end of the last clip, plus the time any
    reverb in use needs to die away."""
    tracks = schemas.audible_tracks(timeline) if tracks is None else tracks
    end, rate = 0, timeline["sample_rate"]
    shared = sum(tail_of(fx) for fx in timeline["master"]["effects"]) if master else 0
    for t in tracks:
        over = sum(tail_of(fx) for fx in t["effects"]) + shared
        for c in t["clips"]:
            if not c["muted"]:
                end = max(end, c["start"] + c["length"] + int(round((sum(tail_of(fx) for fx in c["effects"]) + over) * rate)))
    return end


def build(timeline, files, room, only=None, span=None, out_rate=None):
    """The ffmpeg job for a timeline.

    files     {asset id: (path, format, channels)}
    room      room(size, decay_s) -> path of a reverb impulse file
    only      a track id: that track alone, with its own effects, volume and balance but no master stage (a stem)
    span      (first sample, one past the last) to export part of the timeline
    -> {"inputs": [(path, seconds to skip)], "script": the filter graph, "samples": the length at the timeline's rate,
        "out": the label to write out, "meter": the label the loudest point is measured on}
    """
    rate = timeline["sample_rate"]
    audible = schemas.audible_tracks(timeline)
    tracks = [t for t in audible if t["id"] == only] if only else audible
    total = max(length_of(timeline, audible), schemas.timeline_length(timeline))     # stems all run the full length so they line up
    if span:
        first, last = max(0, int(span[0])), int(span[1])
        if last <= first:
            raise ValueError("The end of the range must be after its start.")
    if total <= 0:
        raise ValueError("There is nothing on the timeline to export.")
    g = _Graph(rate, room)
    made = list(filter(None, (g.track(t, files) for t in tracks)))
    if made:
        stream = g.mix(made)
        if not only:
            stream = g.effects(stream, timeline["master"]["effects"])
            if timeline["master"]["volume_db"]:
                stream = g.run(stream, [f"volume={_gain(timeline['master']['volume_db']):.9f}"])
        stream = g.run(stream, ["asetpts=N/SR/TB", f"apad=whole_len={total}", f"atrim=end_sample={total}"])
    else:
        g.lines.append(f"anullsrc=r={rate}:cl=stereo,aformat=sample_fmts=fltp,atrim=end_sample={total}[silence]")
        stream = "silence"
    samples = total
    if span:
        stream = g.run(stream, [f"apad=whole_len={last}", f"atrim=start_sample={first}:end_sample={last}", "asetpts=N/SR/TB"])
        samples = last - first
    out, meter = g.run(stream, ["asplit=2"], 2)
    meter = g.run(meter, ["astats=measure_perchannel=none:measure_overall=Peak_level"])
    if out_rate and out_rate != rate:
        out = g.run(out, [f"aresample={out_rate}"])
    return {"inputs": g.inputs, "script": ";\n".join(g.lines), "samples": samples, "rate": rate, "out": out, "meter": meter}


# ---------- running it ----------

def encoder(fmt, bits=16, kbps=320):
    if fmt == "wav":
        return ["-c:a", "pcm_s24le" if bits == 24 else "pcm_s16le"]
    if fmt == "flac":
        return ["-c:a", "flac"] + (["-sample_fmt", "s32", "-bits_per_raw_sample", "24"] if bits == 24 else ["-sample_fmt", "s16"])
    if fmt == "mp3":
        return ["-c:a", "libmp3lame", "-b:a", f"{kbps if kbps in MP3_RATES else 320}k"]
    raise ValueError("Export to WAV, FLAC or MP3.")


def command(job, target, script_path, fmt, bits=16, kbps=320):
    args = ["ffmpeg", "-hide_banner", "-nostdin", "-y", "-v", "info", "-nostats", "-progress", "pipe:1"]
    for path, seek in job["inputs"]:
        args += (["-ss", str(seek)] if seek else []) + ["-vn", "-i", path]
    args += (["-/filter_complex", script_path] if features()["major"] >= 7 else ["-filter_complex_script", script_path])
    return args + ["-map", f"[{job['out']}]", "-map_metadata", "-1"] + encoder(fmt, bits, kbps) + [target, "-map", f"[{job['meter']}]", "-f", "null", "-"]


def run(job, target, fmt, bits=16, kbps=320, progress=None, holder=None):
    """Carry out a job from build(). -> {"peak_db": the loudest point before conversion (None if it could not be read)}.
    progress(fraction) is called as it goes; holder, a dict, receives the running process under "process" so it can be stopped."""
    if not shutil.which("ffmpeg"):
        raise ValueError("The server's audio tools are missing. Run update.sh on the server.")
    script, log = target + ".graph", target + ".log"
    with open(script, "w") as f:
        f.write(job["script"])
    try:
        with open(log, "w") as err:
            proc = subprocess.Popen(command(job, target, script, fmt, bits, kbps), stdout=subprocess.PIPE, stderr=err, text=True)
            if holder is not None:
                holder["process"] = proc
            for line in proc.stdout:
                if progress and line.startswith("out_time_us=") and line[12:].strip().lstrip("-").isdigit():
                    progress(min(0.99, max(0.0, int(line[12:]) / 1e6 * job_rate(job) / max(1, job["samples"]))))
            code = proc.wait()
        with open(log, errors="replace") as f:
            said = f.read()
        if code != 0:
            if holder is not None and holder.get("stopped"):
                raise InterruptedError("Stopped.")
            raise ValueError("The export failed: " + (said.strip().splitlines() or ["no reason given"])[-1][-300:])
        found = re.findall(r"Peak level dB:\s*(-?inf|-?[\d.]+)", said)
        peak = None if not found else -120.0 if "inf" in found[-1] else float(found[-1])
        return {"peak_db": peak}
    finally:
        for leftover in (script, log):
            if os.path.exists(leftover):
                os.remove(leftover)


def job_rate(job):
    return job.get("rate", schemas.DEFAULT_RATE)


def read(path, rate=None):
    """A finished file back as (rate, [left samples], [right samples]) in the range -1..1. For tests and checks."""
    args = ["ffmpeg", "-v", "error", "-i", path, "-f", "f32le", "-ac", "2"] + (["-ar", str(rate)] if rate else []) + ["-"]
    out = subprocess.run(args, capture_output=True, timeout=600)
    if out.returncode != 0:
        raise ValueError(out.stderr.decode("utf-8", "replace")[-300:])
    data = array.array("f"); data.frombytes(out.stdout[:len(out.stdout) // 8 * 8])
    if sys.byteorder == "big":
        data.byteswap()
    if rate is None:
        with_rate = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=sample_rate", "-of", "csv=p=0", path],
                                   capture_output=True, text=True, timeout=60).stdout.strip()
        rate = int(with_rate or 0)
    return rate, data[0::2], data[1::2]
