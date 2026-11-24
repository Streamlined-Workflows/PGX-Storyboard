"""Reading audio files: what a file is, and the peak data its waveform is drawn from.

Uses ffmpeg and ffprobe, which run.sh puts in the application's container. Without them (an old
container, or a developer's machine) plain WAV files still work through Python's own reader, and
anything else is refused with a message saying why.

The original file is only ever read here. Nothing in this module writes to it.
"""
import array
import json
import os
import shutil
import struct
import subprocess
import wave

PEAK_RATE = 100                 # peak pairs per second of sound: enough to draw a waveform at any sensible zoom
PEAK_MAGIC = b"SWPK1"           # file header: magic, then peaks-per-second and pair count as two unsigned 32-bit numbers
_DECODE_RATE = 8000             # the waveform is measured from a small mono copy made in memory
FORMATS = {"wav": "wav", "flac": "flac", "mp3": "mp3", "ogg": "ogg", "opus": "opus", "aac": "aac", "mov,mp4,m4a,3gp,3g2,mj2": "m4a", "matroska,webm": "ogg"}
EXTENSIONS = {"wav": "wav", "flac": "flac", "mp3": "mp3", "ogg": "ogg", "oga": "ogg", "opus": "opus", "aac": "aac", "m4a": "m4a", "mp4": "m4a", "webm": "ogg"}


def has_ffmpeg():
    return bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def probe(path):
    """-> {"format", "sample_rate", "channels", "length"} with length in samples at the file's own rate.
    Raises ValueError if the file is not sound this server can read."""
    if has_ffmpeg():
        try:
            out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
                                  "stream=sample_rate,channels,duration,duration_ts,time_base:format=format_name,duration", "-of", "json", path],
                                 capture_output=True, text=True, timeout=60)
            info = json.loads(out.stdout or "{}")
            stream = (info.get("streams") or [None])[0]
        except (OSError, ValueError, subprocess.SubprocessError):
            stream = None
        if not stream or not stream.get("sample_rate"):
            raise ValueError("That file has no sound in it that this server can read.")
        rate = int(stream["sample_rate"])
        seconds = float(stream.get("duration") or (info.get("format") or {}).get("duration") or 0)
        if seconds <= 0:
            raise ValueError("That file's length could not be read.")
        name = (info.get("format") or {}).get("format_name", "")
        return {"format": FORMATS.get(name) or next((v for k, v in FORMATS.items() if name and name.split(",")[0] in k.split(",")), None),
                "sample_rate": rate, "channels": int(stream.get("channels") or 1), "length": int(round(seconds * rate))}
    try:
        with wave.open(path, "rb") as w:
            return {"format": "wav", "sample_rate": w.getframerate(), "channels": w.getnchannels(), "length": w.getnframes()}
    except (wave.Error, EOFError, OSError):
        raise ValueError("Only plain WAV files can be read until the server is updated (run update.sh on it). Other formats need its audio tools.")


def _mono_samples(path):
    """The file as 16-bit mono samples at _DECODE_RATE, as an array of signed shorts."""
    if has_ffmpeg():
        out = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(_DECODE_RATE), "-f", "s16le", "-"],
                             capture_output=True, timeout=1800)
        if out.returncode != 0:
            raise ValueError("That file could not be decoded: " + out.stderr.decode("utf-8", "replace")[-200:])
        data, rate = out.stdout, _DECODE_RATE
    else:
        with wave.open(path, "rb") as w:
            if w.getsampwidth() != 2:
                raise ValueError("Only 16-bit WAV files can be read until the server is updated.")
            raw, channels, rate = w.readframes(w.getnframes()), w.getnchannels(), w.getframerate()
        frames = array.array("h", raw)
        data = array.array("h", (sum(frames[i:i + channels]) // channels for i in range(0, len(frames), channels))).tobytes() if channels > 1 else raw
    samples = array.array("h")
    samples.frombytes(data[:len(data) // 2 * 2])
    return samples, rate


def peaks(path):
    """-> the waveform's peak data as bytes: a small header, then one (lowest, highest) pair of signed bytes
    for every hundredth of a second. An hour of sound is about 720 KB."""
    samples, rate = _mono_samples(path)
    step = max(1, rate // PEAK_RATE)
    pairs = bytearray()
    for i in range(0, len(samples), step):
        chunk = samples[i:i + step]
        pairs.append((min(chunk) >> 8) & 0xFF)
        pairs.append((max(chunk) >> 8) & 0xFF)
    return PEAK_MAGIC + struct.pack("<II", PEAK_RATE, len(pairs) // 2) + bytes(pairs)


def read_peaks(data):
    """-> (pairs per second, [(low, high), …]) from peak bytes. For tests and tools; the browser reads the bytes itself."""
    if data[:5] != PEAK_MAGIC:
        raise ValueError("Not peak data.")
    rate, count = struct.unpack("<II", data[5:13])
    body = array.array("b"); body.frombytes(data[13:13 + count * 2])
    return rate, list(zip(body[0::2], body[1::2]))


def extension(name, probed_format=None):
    """The extension to store a file under: from what the server found in it, else from its name."""
    ext = os.path.splitext(str(name or ""))[1].lower().lstrip(".")
    return probed_format or EXTENSIONS.get(ext)
