import numpy as np
import wave

sample_rate = 44100
duration = 60.0  # seconds
t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)

# Ambient celestial drone frequencies in Hz (C minor 9 chord + ambient harmonics)
freqs = [65.41, 98.0, 130.81, 155.56, 196.0, 233.08, 293.66, 392.0]

signal_l = np.zeros_like(t)
signal_r = np.zeros_like(t)

for idx, f in enumerate(freqs):
    # Gentle phase modulation
    detune_l = f * (1.0 + 0.0015 * np.sin(0.3 * t + idx))
    detune_r = f * (1.0 - 0.0015 * np.cos(0.25 * t + idx))
    amp = (0.22 / (1 + idx * 0.35)) * (0.7 + 0.3 * np.sin(0.4 * t + idx))
    signal_l += amp * np.sin(2 * np.pi * detune_l * t)
    signal_r += amp * np.sin(2 * np.pi * detune_r * t)

# Shimmer
lfo1 = 0.5 + 0.5 * np.sin(2 * np.pi * 0.15 * t)
shimmer = 0.04 * (np.sin(2 * np.pi * 587.33 * t) + np.sin(2 * np.pi * 880.0 * t)) * lfo1
signal_l += shimmer
signal_r += shimmer

# Envelopes
fade_in = np.minimum(1.0, t / 4.0)
fade_out = np.minimum(1.0, (duration - t) / 4.0)
env = fade_in * fade_out

signal_l = np.clip(signal_l * env * 22000, -32767, 32767).astype(np.int16)
signal_r = np.clip(signal_r * env * 22000, -32767, 32767).astype(np.int16)

stereo = np.empty((signal_l.size + signal_r.size,), dtype=np.int16)
stereo[0::2] = signal_l
stereo[1::2] = signal_r

with wave.open("record_demo/space_ambient.wav", "w") as wav:
    wav.setnchannels(2)
    wav.setsampwidth(2)
    wav.setframerate(sample_rate)
    wav.writeframes(stereo.tobytes())

print("Fast ambient audio generated successfully!")
