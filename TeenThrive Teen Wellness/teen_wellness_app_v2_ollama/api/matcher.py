from PIL import Image
import imagehash, numpy as np

MAX_HASH_DISTANCE = 12
MIN_HIST_SIM = 0.80

def compute_hashes(img: Image.Image):
    im = img.convert("RGB")
    return {
        "phash": str(imagehash.phash(im)),
        "ahash": str(imagehash.average_hash(im)),
        "dhash": str(imagehash.dhash(im)),
    }

def _color_histogram(im: Image.Image) -> np.ndarray:
    arr = np.array(im.convert("RGB"))
    hist = []
    for ch in range(3):
        h, _ = np.histogram(arr[:,:,ch], bins=256, range=(0,255))
        hist.append(h.astype(np.float32))
    h = np.concatenate(hist).astype(np.float32)
    h /= (np.linalg.norm(h) + 1e-8)
    return h

def compute_features(img: Image.Image):
    im = img.convert("RGB")
    hashes = compute_hashes(im)
    hist = _color_histogram(im)
    return hashes, hist

def _hash_distance(h1: dict, h2: dict) -> int:
    d = 0
    d += imagehash.hex_to_hash(h1["phash"]) - imagehash.hex_to_hash(h2["phash"])
    d += imagehash.hex_to_hash(h1["ahash"]) - imagehash.hex_to_hash(h2["ahash"])
    d += imagehash.hex_to_hash(h1["dhash"]) - imagehash.hex_to_hash(h2["dhash"])
    return int(d)

def cosine_sim(a, b) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a)*np.linalg.norm(b) + 1e-8))

def match_confidence(q_hash, q_hist, db_hash, db_hist):
    hd = _hash_distance(q_hash, db_hash)
    cs = cosine_sim(q_hist, db_hist)
    if hd <= MAX_HASH_DISTANCE and cs >= MIN_HIST_SIM:
        conf = (1.0 - min(hd / MAX_HASH_DISTANCE, 1.0)) * 0.5 + cs * 0.5
        return True, float(conf), hd, float(cs)
    return False, float(cs*0.5), hd, float(cs)