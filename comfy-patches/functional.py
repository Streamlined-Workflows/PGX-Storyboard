# Minimal torchaudio.functional for the NGC stub: provides resample() only.
import math
import torch


def resample(waveform, orig_freq, new_freq, lowpass_filter_width=6, rolloff=0.99, **kwargs):
    orig_freq, new_freq = int(orig_freq), int(new_freq)
    if orig_freq == new_freq:
        return waveform
    g = math.gcd(orig_freq, new_freq)
    o, n = orig_freq // g, new_freq // g
    base = min(o, n) * rolloff
    width = math.ceil(lowpass_filter_width * o / base)
    dev = waveform.device
    idx = torch.arange(-width, width + o, dtype=torch.float64, device=dev)[None, None] / o
    t = torch.arange(0, -n, -1, dtype=torch.float64, device=dev)[:, None, None] / n + idx
    t = (t * base).clamp(-lowpass_filter_width, lowpass_filter_width)
    window = torch.cos(t * math.pi / lowpass_filter_width / 2) ** 2
    t = t * math.pi
    safe = torch.where(t == 0, torch.ones_like(t), t)
    kernels = torch.where(t == 0, torch.ones_like(t), safe.sin() / safe) * window * (base / o)
    kernels = kernels.to(waveform.dtype)
    shape = waveform.shape
    w = waveform.reshape(-1, shape[-1])
    w = torch.nn.functional.pad(w, (width, width + o))
    out = torch.nn.functional.conv1d(w[:, None], kernels, stride=o)
    out = out.transpose(1, 2).reshape(w.shape[0], -1)
    out = out[..., : int(math.ceil(n * shape[-1] / o))]
    return out.reshape(shape[:-1] + out.shape[-1:])


def __getattr__(name):
    raise RuntimeError("torchaudio is stubbed in this NGC image; only functional.resample is available.")
