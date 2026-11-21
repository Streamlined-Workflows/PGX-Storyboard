"""ComfyUI workflow builders for the storyboard app.

Two engines, both verified on the PGX on 2026-11-21:
  story   - Wan 2.1 image-to-video (16 fps), chained from the last frame for long segments
  singing - Wan 2.1 InfiniteTalk (25 fps), audio-driven, chained with motion-frame overlap
"""
import math
import re

MODELS = {
    "unet_i2v": "Wan2_1-I2V-14B-480p_fp8_e4m3fn_scaled_KJ.safetensors",
    "lora_i2v": "lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors",
    "text_encoder": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
    "vae": "Wan2_1_VAE_bf16.safetensors",
    "clip_vision": "clip_vision_h.safetensors",
    "talk_patch": "wan2.1_infiniteTalk_single_fp16.safetensors",
    "audio_encoder": "wav2vec2-chinese-base_fp16.safetensors",
}

STORY_FPS = 16
STORY_PASS = 81          # frames per pass (5 s)
SING_FPS = 25
SING_PASS = 81           # frames per pass (3.24 s)
SING_MOTION = 9          # frames of overlap fed back into each extension pass
STORY_STEPS = 4
SING_STEPS = 6
NEGATIVE = "blurry, distorted, low quality, static, watermark, text"


class Graph:
    """Tiny helper that hands out node ids and returns [id, output] links."""

    def __init__(self):
        self.nodes = {}
        self._n = 0

    def add(self, class_type, **inputs):
        self._n += 1
        nid = str(self._n)
        self.nodes[nid] = {"class_type": class_type, "inputs": inputs}
        return nid

    def out(self, nid, index=0):
        return [nid, index]


def safe_name(text):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", text or "segment").strip("_")[:40] or "segment"


def story_plan(duration):
    """Return (total_frames, passes) for a story segment of `duration` seconds."""
    total = max(17, int(round(duration * STORY_FPS)))
    if total - STORY_PASS < 8:                       # not worth a whole extra pass for a few frames
        total = min(total, STORY_PASS)
    if total <= STORY_PASS:
        total = min(STORY_PASS, math.ceil((total - 1) / 4) * 4 + 1)   # Wan needs 4n+1 frames
        return total, 1
    passes = 1 + math.ceil((total - STORY_PASS) / (STORY_PASS - 1))
    return total, passes


def singing_plan(duration):
    """Return (total_frames, passes) for a singing segment of `duration` seconds."""
    total = max(25, int(round(duration * SING_FPS)))
    if total - SING_PASS < 8:
        total = min(total, SING_PASS)
    if total <= SING_PASS:
        return total, 1
    passes = 1 + math.ceil((total - SING_PASS) / (SING_PASS - SING_MOTION))
    return total, passes


def _segment_audio(g, song, start, duration):
    if not song:
        return None
    load = g.add("LoadAudio", audio=song)
    trim = g.add("TrimAudioDuration", audio=g.out(load), start_index=float(start), duration=float(duration))
    return g.out(trim)


def _save(g, frames_link, total, fps, audio_link, prefix):
    cut = g.add("ImageFromBatch", image=frames_link, batch_index=0, length=total)
    video_inputs = {"images": g.out(cut), "fps": fps, "bit_depth": 8}
    if audio_link:
        video_inputs["audio"] = audio_link
    video = g.add("CreateVideo", **video_inputs)
    g.add("SaveVideo", video=g.out(video), filename_prefix=prefix, format="auto", codec="auto")


def build_story(seg, song, seed, width=832, height=480, prefix="storyboard/clip"):
    duration = float(seg["end"]) - float(seg["start"])
    total, passes = story_plan(duration)
    g = Graph()
    unet = g.add("UNETLoader", unet_name=MODELS["unet_i2v"], weight_dtype="default")
    lora = g.add("LoraLoaderModelOnly", lora_name=MODELS["lora_i2v"], strength_model=1.0, model=g.out(unet))
    model = g.add("ModelSamplingSD3", shift=8, model=g.out(lora))
    clip = g.add("CLIPLoader", clip_name=MODELS["text_encoder"], type="wan", device="default")
    pos = g.add("CLIPTextEncode", clip=g.out(clip), text=seg.get("prompt") or "")
    neg = g.add("CLIPTextEncode", clip=g.out(clip), text=NEGATIVE)
    vae = g.add("VAELoader", vae_name=MODELS["vae"])
    cv = g.add("CLIPVisionLoader", clip_name=MODELS["clip_vision"])
    begin = g.add("LoadImage", image=seg["begin_image"])

    start_link, acc = g.out(begin), None
    for i in range(passes):
        length = total if passes == 1 else STORY_PASS
        cve = g.add("CLIPVisionEncode", clip_vision=g.out(cv), image=start_link, crop="none")
        i2v = g.add("WanImageToVideo", positive=g.out(pos), negative=g.out(neg), vae=g.out(vae),
                    width=width, height=height, length=length, batch_size=1,
                    clip_vision_output=g.out(cve), start_image=start_link)
        ks = g.add("KSampler", seed=seed + i, steps=STORY_STEPS, cfg=1, sampler_name="euler", scheduler="simple",
                   denoise=1.0, model=g.out(model), positive=g.out(i2v, 0), negative=g.out(i2v, 1),
                   latent_image=g.out(i2v, 2))
        dec = g.add("VAEDecode", samples=g.out(ks), vae=g.out(vae))
        if acc is None:
            acc = g.out(dec)
        else:
            fresh = g.add("ImageFromBatch", image=g.out(dec), batch_index=1, length=length - 1)
            acc = g.out(g.add("ImageBatch", image1=acc, image2=g.out(fresh)))
        if i < passes - 1:
            last = g.add("ImageFromBatch", image=g.out(dec), batch_index=length - 1, length=1)
            start_link = g.out(last)

    _save(g, acc, total, STORY_FPS, _segment_audio(g, song, seg["start"], duration), prefix)
    return g.nodes


def build_singing(seg, song, seed, width=832, height=480, prefix="storyboard/clip"):
    if not song:
        raise ValueError("A singing segment needs a song loaded.")
    duration = float(seg["end"]) - float(seg["start"])
    total, passes = singing_plan(duration)
    g = Graph()
    unet = g.add("UNETLoader", unet_name=MODELS["unet_i2v"], weight_dtype="default")
    model = g.add("LoraLoaderModelOnly", lora_name=MODELS["lora_i2v"], strength_model=1.0, model=g.out(unet))
    patch = g.add("ModelPatchLoader", name=MODELS["talk_patch"])
    clip = g.add("CLIPLoader", clip_name=MODELS["text_encoder"], type="wan", device="default")
    pos = g.add("CLIPTextEncode", clip=g.out(clip), text=seg.get("prompt") or "")
    neg = g.add("ConditioningZeroOut", conditioning=g.out(pos))
    vae = g.add("VAELoader", vae_name=MODELS["vae"])
    begin = g.add("LoadImage", image=seg["begin_image"])
    audio = _segment_audio(g, song, seg["start"], duration)
    enc_loader = g.add("AudioEncoderLoader", audio_encoder_name=MODELS["audio_encoder"])
    enc = g.add("AudioEncoderEncode", audio_encoder=g.out(enc_loader), audio=audio)
    sampler = g.add("KSamplerSelect", sampler_name="euler")

    acc = None
    for i in range(passes):
        inputs = dict(mode="single_speaker", width=width, height=height, length=SING_PASS,
                      motion_frame_count=SING_MOTION, audio_scale=1, model=g.out(model),
                      model_patch=g.out(patch), positive=g.out(pos), negative=g.out(neg), vae=g.out(vae),
                      audio_encoder_output_1=g.out(enc), start_image=g.out(begin))
        if acc is not None:
            inputs["previous_frames"] = acc
        talk = g.add("WanInfiniteTalkToVideo", **inputs)
        guider = g.add("CFGGuider", cfg=1, model=g.out(talk, 0), positive=g.out(talk, 1), negative=g.out(talk, 2))
        sigmas = g.add("BasicScheduler", scheduler="normal", steps=SING_STEPS, denoise=1, model=g.out(talk, 0))
        noise = g.add("RandomNoise", noise_seed=seed + i)
        samp = g.add("SamplerCustomAdvanced", noise=g.out(noise), guider=g.out(guider), sampler=g.out(sampler),
                     sigmas=g.out(sigmas), latent_image=g.out(talk, 3))
        dec = g.add("VAEDecode", samples=g.out(samp), vae=g.out(vae))
        if acc is None:
            acc = g.out(dec)
        else:
            # An extension pass regenerates the motion frames first; drop them so audio stays in step.
            fresh = g.add("ImageFromBatch", image=g.out(dec), batch_index=SING_MOTION, length=SING_PASS - SING_MOTION)
            acc = g.out(g.add("ImageBatch", image1=acc, image2=g.out(fresh)))

    _save(g, acc, total, SING_FPS, audio, prefix)
    return g.nodes


def plan(seg):
    """How much work a segment is: passes and sampler steps per pass (used for progress bars)."""
    duration = float(seg["end"]) - float(seg["start"])
    if seg.get("type") == "singing":
        return {"passes": singing_plan(duration)[1], "steps": SING_STEPS}
    return {"passes": story_plan(duration)[1], "steps": STORY_STEPS}


def build(seg, song, seed, **kw):
    if not seg.get("begin_image"):
        raise ValueError("This segment has no begin shot yet.")
    if float(seg["end"]) <= float(seg["start"]):
        raise ValueError("Segment end must be after its start.")
    if seg.get("type") == "singing":
        return build_singing(seg, song, seed, **kw)
    return build_story(seg, song, seed, **kw)
