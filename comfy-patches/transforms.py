# Minimal torchaudio.transforms for the NGC stub: provides MelSpectrogram only.
import math
import torch


def _hz_to_mel(freq, mel_scale):
    if mel_scale == "htk":
        return 2595.0 * math.log10(1.0 + freq / 700.0)
    f_sp, min_log_hz = 200.0 / 3, 1000.0            # slaney
    min_log_mel, logstep = min_log_hz / f_sp, math.log(6.4) / 27.0
    return min_log_mel + math.log(freq / min_log_hz) / logstep if freq >= min_log_hz else freq / f_sp


def _mel_to_hz(mels, mel_scale):
    if mel_scale == "htk":
        return 700.0 * (10.0 ** (mels / 2595.0) - 1.0)
    f_sp, min_log_hz = 200.0 / 3, 1000.0
    min_log_mel, logstep = min_log_hz / f_sp, math.log(6.4) / 27.0
    freqs = f_sp * mels
    log_t = mels >= min_log_mel
    freqs[log_t] = min_log_hz * torch.exp(logstep * (mels[log_t] - min_log_mel))
    return freqs


def _mel_filterbank(n_freqs, f_min, f_max, n_mels, sample_rate, norm, mel_scale):
    all_freqs = torch.linspace(0, sample_rate // 2, n_freqs)
    m_pts = torch.linspace(_hz_to_mel(f_min, mel_scale), _hz_to_mel(f_max, mel_scale), n_mels + 2)
    f_pts = _mel_to_hz(m_pts, mel_scale)
    f_diff = f_pts[1:] - f_pts[:-1]
    slopes = f_pts.unsqueeze(0) - all_freqs.unsqueeze(1)
    down = (-1.0 * slopes[:, :-2]) / f_diff[:-1]
    up = slopes[:, 2:] / f_diff[1:]
    fb = torch.max(torch.zeros(1), torch.min(down, up))
    if norm == "slaney":
        fb = fb * (2.0 / (f_pts[2:n_mels + 2] - f_pts[:n_mels])).unsqueeze(0)
    return fb                                        # (n_freqs, n_mels)


class MelSpectrogram(torch.nn.Module):
    def __init__(self, sample_rate=16000, n_fft=400, win_length=None, hop_length=None, f_min=0.0, f_max=None,
                 pad=0, n_mels=128, window_fn=torch.hann_window, power=2.0, normalized=False, wkwargs=None,
                 center=True, pad_mode="reflect", onesided=None, norm=None, mel_scale="htk"):
        super().__init__()
        self.n_fft = n_fft
        self.win_length = win_length if win_length is not None else n_fft
        self.hop_length = hop_length if hop_length is not None else self.win_length // 2
        self.pad, self.power, self.normalized = pad, power, normalized
        self.center, self.pad_mode = center, pad_mode
        self.register_buffer("window", window_fn(self.win_length, **(wkwargs or {})), persistent=False)
        f_max = float(f_max) if f_max is not None else float(sample_rate // 2)
        self.register_buffer("fb", _mel_filterbank(n_fft // 2 + 1, f_min, f_max, n_mels, sample_rate, norm, mel_scale),
                             persistent=False)

    def forward(self, waveform):
        if self.pad > 0:
            waveform = torch.nn.functional.pad(waveform, (self.pad, self.pad))
        shape = waveform.shape
        flat = waveform.reshape(-1, shape[-1])
        window = self.window.to(device=flat.device, dtype=flat.dtype)
        spec = torch.stft(flat, n_fft=self.n_fft, hop_length=self.hop_length, win_length=self.win_length,
                          window=window, center=self.center, pad_mode=self.pad_mode, normalized=False,
                          onesided=True, return_complex=True)
        if self.normalized:
            spec = spec / window.pow(2.0).sum().sqrt()
        spec = spec.abs() if self.power == 1.0 else spec.abs().pow(self.power)
        mel = torch.matmul(spec.transpose(-1, -2), self.fb.to(device=spec.device, dtype=spec.dtype)).transpose(-1, -2)
        return mel.reshape(shape[:-1] + mel.shape[-2:])


def __getattr__(name):
    raise RuntimeError("torchaudio is stubbed in this NGC image; only transforms.MelSpectrogram is available.")
