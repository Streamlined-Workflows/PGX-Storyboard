#!/usr/bin/env python3
"""One loaded speech model. Started by service.py with the Python environment that model needs, and stopped
to give its memory back: ending the process is the only way to be sure the graphics card lets go.

    worker.py qwen <model folder>
    worker.py ming <model folder>

It reads one JSON request per line on standard input and answers with one JSON line each. Everything the
libraries print goes to the error stream, so the answers stay clean.

    {"op": "speak", "out": "/tmp/x.wav", "text": "...", "language": "English",
     "mode": "clone" | "design" | "preset", "ref_audio": path, "ref_text": "...", "instruct": "...", "speaker": "..."}
 -> {"ok": true, "sample_rate": 24000, "seconds": 3.2, "took": 1.9, "memory": bytes held on the graphics card}
"""
import json
import os
import sys
import time

answers = os.fdopen(os.dup(1), "w")
os.dup2(2, 1)                                   # anything printed from here on goes to the error stream


def say(**fields):
    answers.write(json.dumps(fields) + "\n")
    answers.flush()


def held():
    try:
        import torch
        return int(torch.cuda.max_memory_allocated()) if torch.cuda.is_available() else 0
    except Exception:
        return 0


def write(path, wave, rate):
    """wave: one-dimensional samples (a numpy array, or anything numpy can read)."""
    import numpy as np
    import soundfile
    wave = np.asarray(wave, dtype="float32").reshape(-1)
    soundfile.write(path, wave, rate, subtype="PCM_16")
    return len(wave) / float(rate)


class Qwen:
    def __init__(self, folder):
        from faster_qwen3_tts import FasterQwen3TTS
        self.model = FasterQwen3TTS.from_pretrained(folder)
        self.kind = getattr(self.model.model.model, "tts_model_type", "") or ""
        try:
            self.speakers = sorted(self.model.model.get_supported_speakers() or [])
        except Exception:
            self.speakers = []

    def speak(self, r):
        language = r.get("language") or "English"
        if r["mode"] == "clone":
            # With a transcript of the recording the copy is closer; without one, only the character of the voice is taken.
            audio, rate = self.model.generate_voice_clone(text=r["text"], language=language, ref_audio=r["ref_audio"],
                                                          ref_text=r.get("ref_text") or "", xvec_only=not r.get("ref_text"))
        elif r["mode"] == "design":
            audio, rate = self.model.generate_voice_design(text=r["text"], instruct=r["instruct"], language=language)
        else:
            speaker = r.get("speaker") or (self.speakers[0] if self.speakers else "")
            audio, rate = self.model.generate_custom_voice(text=r["text"], speaker=speaker, language=language, instruct=r.get("instruct") or None)
        import numpy as np
        return np.concatenate([np.asarray(a).reshape(-1) for a in audio]) if isinstance(audio, (list, tuple)) else audio, rate


class Ming:
    def __init__(self, folder):
        source = os.environ.get("MING_SOURCE", "/opt/src/ming")
        sys.path.insert(0, source)
        os.chdir(source)                        # it finds some of its own files relative to where it runs
        import soundfile
        import torch
        import torchaudio

        # Its code reads and writes sound through torchaudio calls that newer torchaudio no longer provides in
        # the same form. Reading with soundfile directly gives it the same thing: (channels, samples) and the rate.
        def load(path, *args, **kwargs):
            data, rate = soundfile.read(path, dtype="float32", always_2d=True)
            return torch.from_numpy(data.T.copy()), rate
        torchaudio.load = load
        from ming_tts import MingTTS
        self.model = MingTTS(folder, text_normalization=False)       # the optional text normaliser is not installed
        self.speakers = ["US_Emma", "UK_George", "UK_Charlotte"]     # the English built-in voices its makers recommend

    def speak(self, r):
        language = r.get("language") or "English"
        if r["mode"] == "clone":
            if not r.get("ref_text"):
                raise ValueError("This model needs the words spoken in the recording as well as the recording.")
            wave = self.model.synthesize(task="TTS", text=r["text"], language_id=language, prompt_wav_path=r["ref_audio"],
                                         prompt_text=r["ref_text"], use_spk_emb=True)
        elif r["mode"] == "design":
            wave = self.model.synthesize(task="FREEFORM", text=r["text"], instruction=r["instruct"], use_zero_spk_emb=True)
        else:
            wave = self.model.synthesize(task="IP", text=r["text"], controls={"ip": r.get("speaker") or self.speakers[0]}, use_zero_spk_emb=True)
        return wave.detach().float().cpu().numpy().reshape(-1), self.model.sample_rate


def main():
    engine, folder = sys.argv[1], sys.argv[2]
    try:
        model = {"qwen": Qwen, "ming": Ming}[engine](folder)
    except BaseException as e:
        say(ready=False, error=f"{type(e).__name__}: {e}"[:600])
        return 1
    say(ready=True, speakers=getattr(model, "speakers", []), kind=getattr(model, "kind", ""), memory=held())
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            r = json.loads(line)
            started = time.time()
            wave, rate = model.speak(r)
            seconds = write(r["out"], wave, int(rate))
            say(ok=True, sample_rate=int(rate), seconds=round(seconds, 3), took=round(time.time() - started, 2), memory=held())
        except BaseException as e:
            if isinstance(e, (KeyboardInterrupt, SystemExit)):
                raise
            say(ok=False, error=f"{type(e).__name__}: {e}"[:600])
    return 0


if __name__ == "__main__":
    sys.exit(main())
