import wave
import math
import struct

sample_rate = 44100
duration = 55.0  # seconds
num_samples = int(sample_rate * duration)

# Ambient celestial drone frequencies in Hz (e.g. C minor 9 chord with gentle pads)
# Low drone C2 (65.41), G2 (98.0), Eb3 (155.56), Bb3 (233.08), D4 (293.66), G4 (392.0)
freqs = [65.41, 98.0, 130.81, 155.56, 196.0, 233.08, 293.66, 392.0]

with wave.open("record_demo/space_ambient.wav", "w") as wav:
    wav.setnchannels(2)  # Stereo
    wav.setsampwidth(2)  # 16-bit
    wav.setframerate(sample_rate)

    frames = bytearray()
    for i in range(num_samples):
        t = i / sample_rate
        # slow pulsing LFO
        lfo1 = 0.5 + 0.5 * math.sin(2 * math.pi * 0.15 * t)
        lfo2 = 0.5 + 0.5 * math.cos(2 * math.pi * 0.08 * t)
        lfo3 = 0.5 + 0.5 * math.sin(2 * math.pi * 0.05 * t)
        
        # Fade in and fade out
        fade_in = min(1.0, t / 4.0)
        fade_out = min(1.0, (duration - t) / 4.0)
        envelope = fade_in * fade_out

        sample_l = 0.0
        sample_r = 0.0

        for idx, f in enumerate(freqs):
            detune_l = f * (1.0 + 0.0015 * math.sin(0.3 * t + idx))
            detune_r = f * (1.0 - 0.0015 * math.cos(0.25 * t + idx))
            amp = (0.22 / (1 + idx * 0.35)) * (0.7 + 0.3 * math.sin(0.4 * t + idx))
            
            # Subtly detuned stereo spread
            sample_l += amp * math.sin(2 * math.pi * detune_l * t)
            sample_r += amp * math.sin(2 * math.pi * detune_r * t)

        # High harmonic celestial shimmer
        shimmer = 0.03 * (math.sin(2 * math.pi * 587.33 * t) + math.sin(2 * math.pi * 880.0 * t)) * lfo1
        sample_l += shimmer
        sample_r += shimmer * lfo2

        # Master gain and clipping guard
        val_l = int(max(-32767, min(32767, sample_l * envelope * 24000)))
        val_r = int(max(-32767, min(32767, sample_r * envelope * 24000)))

        frames.extend(struct.pack("<hh", val_l, val_r))

    wav.writeframes(frames)
print("Generated record_demo/space_ambient.wav successfully!")
