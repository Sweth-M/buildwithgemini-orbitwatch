import numpy as np
import wave
import struct

sample_rate = 44100
duration = 80.0  # 80 seconds
num_samples = int(sample_rate * duration)
t = np.linspace(0, duration, num_samples, endpoint=False)
audio = np.zeros(num_samples)

# Ambient Space Drone: Deep resonant fundamentals with slow evolving detuned pads and shimmering harmonics
# Frequencies: Deep sub-bass (55 Hz - A1), fifth (82.4 Hz - E2), octave (110 Hz - A2), minor third (130.8 Hz - C3), shimmering fifth (164.8 Hz - E3), ethereal octave (220 Hz - A3), high crystal (440 Hz & 659.25 Hz)
layers = [
    {"freq": 55.0, "amp": 0.22, "lfo_rate": 0.05, "harmonics": [1.0, 0.4]},
    {"freq": 55.25, "amp": 0.18, "lfo_rate": 0.08, "harmonics": [1.0]}, # slight detune for cosmic chorusing
    {"freq": 82.4, "amp": 0.16, "lfo_rate": 0.07, "harmonics": [1.0, 0.3]},
    {"freq": 110.0, "amp": 0.14, "lfo_rate": 0.04, "harmonics": [1.0, 0.2, 0.1]},
    {"freq": 130.81, "amp": 0.12, "lfo_rate": 0.06, "harmonics": [1.0, 0.15]},
    {"freq": 164.81, "amp": 0.10, "lfo_rate": 0.09, "harmonics": [1.0]},
    {"freq": 220.0, "amp": 0.08, "lfo_rate": 0.03, "harmonics": [1.0, 0.2]},
    {"freq": 440.0, "amp": 0.04, "lfo_rate": 0.12, "harmonics": [1.0]},
    {"freq": 659.25, "amp": 0.03, "lfo_rate": 0.10, "harmonics": [1.0]},
]

for layer in layers:
    base_freq = layer["freq"]
    lfo = 0.6 + 0.4 * np.sin(2 * np.pi * layer["lfo_rate"] * t)
    for h_idx, h_weight in enumerate(layer["harmonics"]):
        freq = base_freq * (h_idx + 1)
        audio += layer["amp"] * h_weight * lfo * np.sin(2 * np.pi * freq * t)

# Subtle cosmic shimmer / stellar wind (filtered noise with slow sweeps)
cosmic_wind = np.random.normal(0, 0.015, num_samples)
wind_lfo = 0.5 + 0.5 * np.sin(2 * np.pi * 0.03 * t)
audio += cosmic_wind * wind_lfo

# Smooth fade in and fade out
fade_len = int(sample_rate * 3.0)
fade_in = np.linspace(0, 1, fade_len)
fade_out = np.linspace(1, 0, fade_len)
audio[:fade_len] *= fade_in
audio[-fade_len:] *= fade_out

# Normalize to comfortable level
audio = audio / np.max(np.abs(audio)) * 0.45

wav_file = "space_ambient.wav"
with wave.open(wav_file, "w") as f:
    f.setnchannels(1)
    f.setsampwidth(2)
    f.setframerate(sample_rate)
    for s in audio:
        val = int(s * 32767.0)
        f.writeframes(struct.pack("<h", max(-32768, min(32767, val))))

print("Generated space_ambient.wav successfully!")
