"""Build a short, deterministic cascade of metallic coin impacts (standard library)."""
import math
from pathlib import Path
import random
import struct
import wave

rate = 44100
rng = random.Random(34)
samples = [0.0] * int(rate * 1.45)
for index in range(30):
    at = int(rate * (0.015 + index * 0.032 + rng.uniform(0, 0.035)))
    pitch = rng.uniform(1700, 3600)
    decay = rng.uniform(0.035, 0.075)
    strength = rng.uniform(0.12, 0.22) * (1 - index / 65)
    phases = [rng.uniform(0, math.tau) for _ in range(4)]
    for n in range(int(rate * 0.32)):
        t = n / rate
        envelope = min(1, t / 0.0008) * math.exp(-t / decay)
        metal = sum(math.sin(math.tau * pitch * ratio * t + phase) / (j + 1)
                    for j, (ratio, phase) in enumerate(zip((1, 1.43, 1.97, 2.61), phases)))
        transient = rng.uniform(-1, 1) * math.exp(-t / 0.006) * 0.3
        if at + n < len(samples):
            samples[at + n] += strength * (metal * envelope + transient)
peak = max(abs(value) for value in samples)
destination = Path(__file__).resolve().parents[1] / "assets/audio/coin-rattle.wav"
with wave.open(str(destination), "wb") as audio:
    audio.setnchannels(1)
    audio.setsampwidth(2)
    audio.setframerate(rate)
    audio.writeframes(b"".join(struct.pack("<h", int(value / peak * 25000)) for value in samples))
print(destination)
