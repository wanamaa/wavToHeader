# -*- coding: utf-8 -*-
"""
wav_to_header.py - Converts a WAV file into a C header (.h) file containing
a raw 8-bit unsigned PCM sample array, for embedding directly into flash
on a board with no SD card / filesystem.

Author: AW Labs

Usage:
    python wav_to_header.py input.wav output.h VARIABLE_NAME [--rate 8000]

Output is mono, 8-bit unsigned PCM at the target sample rate (8000 Hz
default - plenty for a hum/hit sound effect, and keeps flash usage small:
8000 Hz * 1 byte/sample = 8KB per second of audio).

Requires: numpy (pip install numpy --break-system-packages if needed).
Supports 8, 16, and 32-bit integer PCM WAV input. If your WAV is 24-bit
or float format and this errors out, re-export it as standard 16-bit PCM
WAV in Audacity/your DAW of choice - that format is universally supported
and avoids ambiguity here.
"""

__author__ = "A. Wanamaker"
__copyright__ = "Copyright 2026, AW Labs"
__version__ = "1.0.0"
__license__ = "MIT"

import wave
import numpy as np
import argparse
import os


def read_wav_as_float(path):
    with wave.open(path, 'rb') as wf:
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)

    print(f"Input: {path}")
    print(f"  channels={n_channels}, sample_width={sampwidth} bytes, "
          f"frame_rate={framerate} Hz, frames={n_frames}")

    if sampwidth == 1:
        # 8-bit WAV PCM is unsigned (0-255), center at 128
        data = np.frombuffer(raw, dtype=np.uint8).astype(np.float32)
        data = (data - 128) / 128.0
    elif sampwidth == 2:
        data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    elif sampwidth == 4:
        data = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
    else:
        raise ValueError(
            f"Unsupported sample width: {sampwidth} bytes. "
            "Re-export the WAV as standard 16-bit PCM and try again."
        )

    if n_channels > 1:
        data = data.reshape(-1, n_channels).mean(axis=1)  # downmix to mono

    return data, framerate


def resample(data, orig_rate, target_rate):
    if orig_rate == target_rate:
        return data
    duration = len(data) / orig_rate
    n_target = max(1, int(round(duration * target_rate)))
    x_old = np.linspace(0, duration, num=len(data), endpoint=False)
    x_new = np.linspace(0, duration, num=n_target, endpoint=False)
    return np.interp(x_new, x_old, data)


def normalize(data, target_peak=0.98):
    """Scale so the loudest sample hits target_peak (just under full scale
    to avoid clipping on rounding). No-op if the file is silent."""
    peak = np.max(np.abs(data))
    if peak < 1e-6:
        return data
    return data * (target_peak / peak)


def convert(input_path, output_path, var_name, target_rate, do_normalize=True, gain=1.0):
    data, framerate = read_wav_as_float(input_path)
    data = resample(data, framerate, target_rate)

    if do_normalize:
        data = normalize(data)
        print("Applied peak normalization")

    if gain != 1.0:
        data = data * gain
        print(f"Applied extra gain: {gain}x")

    data = np.clip(data, -1.0, 1.0)  # protect against clipping from --gain
    pcm8 = np.round((data * 127.0) + 128.0).astype(np.uint8)

    sample_count = len(pcm8)
    duration_s = sample_count / target_rate
    print(f"Output: {sample_count} bytes, {duration_s:.2f} sec at {target_rate} Hz mono 8-bit")

    guard = os.path.basename(output_path).upper().replace('.', '_').replace('-', '_')

    with open(output_path, 'w') as f:
        f.write(f"#ifndef {guard}\n#define {guard}\n\n#include <stdint.h>\n\n")
        f.write(f"// Auto-generated from {os.path.basename(input_path)}\n")
        f.write(f"// {target_rate} Hz, mono, 8-bit unsigned PCM, {duration_s:.2f} sec\n\n")
        f.write(f"const unsigned long {var_name}_LENGTH = {sample_count}UL;\n")
        f.write(f"const unsigned long {var_name}_SAMPLE_RATE = {target_rate}UL;\n\n")
        f.write(f"const uint8_t {var_name}[] = {{\n")

        for i in range(0, sample_count, 20):
            chunk = pcm8[i:i+20]
            line = ", ".join(str(b) for b in chunk)
            f.write(f"  {line},\n")

        f.write("};\n\n")
        f.write(f"#endif // {guard}\n")

    print(f"Wrote {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert WAV to a C header array for flash-embedded playback")
    parser.add_argument("input_wav")
    parser.add_argument("output_header")
    parser.add_argument("variable_name")
    parser.add_argument("--rate", type=int, default=8000, help="Target sample rate (default 8000 Hz)")
    parser.add_argument("--no-normalize", action="store_true",
                         help="Skip peak normalization (default: normalization is ON)")
    parser.add_argument("--gain", type=float, default=1.0,
                         help="Extra gain multiplier applied after normalization, e.g. 1.5 for +50%%. "
                              "Values above ~1.2-1.5 will likely start clipping/distorting - "
                              "try a modest value first and listen before pushing higher.")
    args = parser.parse_args()

    convert(args.input_wav, args.output_header, args.variable_name, args.rate,
            do_normalize=not args.no_normalize, gain=args.gain)
