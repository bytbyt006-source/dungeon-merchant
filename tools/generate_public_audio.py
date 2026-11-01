"""Generate original public-release effects using only mathematical synthesis."""
import math
from pathlib import Path
import random
import struct
import wave

ROOT = Path(__file__).resolve().parents[1]
RATE = 22050


def write_effect(name, seconds, kind):
    """Mix damped tones and deterministic noise; no recordings are sampled."""
    rng = random.Random(name)
    samples = [0.0] * int(RATE * seconds)
    counts = {"button": 1, "door": 3, "pouch": 8, "dice": 18}
    for index in range(counts[kind]):
        at = index * seconds / (counts[kind] + 1)
        pitch = rng.uniform(600, 2400) if kind in ("button", "dice") else rng.uniform(130, 700)
        decay = .035 if kind in ("button", "dice") else .12
        for n in range(min(int(RATE * .45), len(samples) - int(at * RATE))):
            t = n / RATE
            envelope = min(1, t / .002) * math.exp(-t / decay)
            tone = math.sin(math.tau * pitch * t) + .35 * math.sin(math.tau * pitch * 1.47 * t)
            noise = rng.uniform(-1, 1) * (1 if kind == "dice" else .4)
            samples[int(at * RATE) + n] += (tone + noise) * envelope
    peak = max(1, max(abs(value) for value in samples))
    path = ROOT / "assets/audio" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(RATE)
        output.writeframes(b"".join(struct.pack("<h", round(value / peak * 18000)) for value in samples))


if __name__ == "__main__":
    for spec in [("button.wav", .10, "button"), ("customer-arrival.wav", .65, "door"),
                 ("payment-pouch.wav", .45, "pouch"), ("dice-roll.wav", 1.2, "dice")]:
        write_effect(*spec)
    print("Generated four original public-release sound effects.")
