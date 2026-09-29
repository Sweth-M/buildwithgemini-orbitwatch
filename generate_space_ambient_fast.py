import numpy as np
import wave

sample_rate = 22050
duration = 80.0
num_samples = int(sample_rate * duration)
t = np.linspace(0, duration, num_samples, endpoint=False, dtype=np.float32)
audio = np.zeros(num_samples, dtype=np.float32)

layers = [
    (55.0, 0.22, 0.05),
    (55.25, 0.18, 0.08),
    (82.4, 0.16, 0.07),
    (110.0, 0.14, 0.04),
    (130.81, 0.12, 0.06),
    (164.81, 0.10, 0.09),
    (220.0, 0.08, 0.03),
    (440.0, 0.04, 0.12),
]

for freq, amp, lfo_rate in layers:
    lfo = 0.6 + 0.4 * np.sin(2 * np.pi * lfo_rate * t)
    audio += amp * lfo * np.sin(2 * np.pi * freq * t)

# Shimmer
noise = np.random.normal(0, 0.008, num_samples).astype(np.float32)
audio += noise

fade_len = int(sample_rate * 2.5)
audio[:fade_len] *= np.linspace(0, 1, fade_len, dtype=np.float32)
audio[-fade_len:] *= np.linspace(1, 0, fade_len, dtype=np.float32)

audio = (audio / np.max(np.abs(audio)) * 0.45 * 32767).astype(np.int16)

with wave.open("space_ambient.wav", "w") as f:
    f.setnchannels(1)
    f.setsampwidth(2)
    f.setframerate(sample_rate)
    f.writeframes(audio.tobytes())

print("Fast space ambient audio generated successfully!")
