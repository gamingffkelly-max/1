import torch
from PIL import Image, ImageDraw
from config import SD_MODEL, STYLE_LONG, STYLE_SHORT
torch.set_num_threads(4)
_p = None

def _pipe():
    global _p
    if _p is None:
        from diffusers import DiffusionPipeline
        _p = DiffusionPipeline.from_pretrained(SD_MODEL, torch_dtype=torch.float32, safety_checker=None, requires_safety_checker=False)
        _p.to("cuda" if torch.cuda.is_available() else "cpu")
    return _p

def _fallback(w, h):
    img = Image.new("RGB", (w, h)); d = ImageDraw.Draw(img)
    for y in range(h): d.line([(0, y), (w, y)], fill=(10 + y * 40 // h, 20 + y * 60 // h, 50 + y * 90 // h))
    return img

def image(prompt, path, vertical, seed, big=False):
    w, h = (288, 512) if vertical else ((768, 432) if big else (512, 288))
    try:
        img = _pipe()(prompt=f"{prompt}, {STYLE_SHORT if vertical else STYLE_LONG}", num_inference_steps=4, guidance_scale=8.0,
                      width=w, height=h, generator=torch.Generator().manual_seed(seed)).images[0]
        if img.convert("L").getextrema()[1] < 8: raise ValueError("black image")
    except Exception:
        img = _fallback(w, h)
    img.save(path)
