# wav_to_header

Convert a WAV file into a C header (`.h`) containing a raw 8-bit unsigned PCM sample array, ready to embed directly in flash on boards with no SD card or filesystem.

![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

Ideal for short sound effects (hums, hits, beeps, UI clicks) on microcontroller projects where you just want `const uint8_t sound[]` and a playback loop.

## Features

- Reads 8-, 16-, and 32-bit integer PCM WAV files
- Downmixes stereo/multichannel to mono
- Resamples to any target rate (default **8000 Hz**)
- Peak normalization on by default, with optional extra gain
- Clips safely so `--gain` can never wrap around
- Emits a self-contained header with include guard, length, and sample rate constants

## Requirements

- Python 3.8+
- [NumPy](https://numpy.org/)

```bash
pip install numpy
```

> On some Linux distributions you may need `pip install numpy --break-system-packages`, or use a virtual environment.

## Usage

```bash
python wav_to_header.py <input.wav> <output.h> <VARIABLE_NAME> [options]
```

| Argument | Description |
|---|---|
| `input_wav` | Path to the source WAV file |
| `output_header` | Path for the generated `.h` file |
| `variable_name` | Base name for the generated C symbols (must be a valid C identifier) |

### Options

| Option | Default | Description |
|---|---|---|
| `--rate N` | `8000` | Target sample rate in Hz |
| `--no-normalize` | off (normalization **on**) | Skip peak normalization |
| `--gain X` | `1.0` | Extra gain multiplier applied *after* normalization (e.g. `1.5` for +50%). Values above ~1.2–1.5 will likely clip and distort, so start modest and listen before pushing higher. |

### Examples

Basic conversion at the default 8 kHz:

```bash
python wav_to_header.py hum.wav hum.h HUM_SOUND
```

Higher sample rate for clearer audio (uses more flash):

```bash
python wav_to_header.py hit.wav hit.h HIT_SOUND --rate 16000
```

Keep the original dynamics and add a little boost:

```bash
python wav_to_header.py hit.wav hit.h HIT_SOUND --no-normalize --gain 1.2
```

Sample console output:

```
Input: hum.wav
  channels=2, sample_width=2 bytes, frame_rate=44100 Hz, frames=88200
Applied peak normalization
Output: 16000 bytes, 2.00 sec at 8000 Hz mono 8-bit
Wrote hum.h
```

## Output format

Given `python wav_to_header.py hum.wav hum.h HUM_SOUND`, the generated `hum.h` looks like:

```c
#ifndef HUM_H
#define HUM_H

// Auto-generated from hum.wav
// 8000 Hz, mono, 8-bit unsigned PCM, 2.00 sec

const unsigned long HUM_SOUND_LENGTH = 16000UL;
const unsigned long HUM_SOUND_SAMPLE_RATE = 8000UL;

const uint8_t HUM_SOUND[] = {
  128, 131, 135, 140, ...
};

#endif // HUM_H
```

- **Samples** are unsigned 8-bit, with **128 = silence**. Values range from about 1 to 255.
- **`_LENGTH`** is the number of samples (equal to the number of bytes).
- **`_SAMPLE_RATE`** is the rate you need to play the data back at.
- The include guard is derived from the output filename.

## Flash budget

At 8-bit mono, storage is simply `sample_rate × seconds` bytes:

| Sample rate | Per second of audio |
|---|---|
| 8,000 Hz | 8 KB |
| 11,025 Hz | ~11 KB |
| 16,000 Hz | 16 KB |

8 kHz is plenty for effects like hums and hits, and keeps flash usage small.

## Using the header in firmware

Include the generated file and step through the array at `_SAMPLE_RATE`, writing each sample to your DAC, PWM output, or an amplifier input. The sketch below is a minimal, board-agnostic illustration. Swap `writeSample()` for whatever output your hardware provides (DAC, PWM, I2S, etc.).

```cpp
#include <stdint.h>
#include "hum.h"

void writeSample(uint8_t s) {
  // TODO: output to your DAC / PWM pin
  analogWrite(A0, s);
}

void playSound() {
  const uint32_t periodUs = 1000000UL / HUM_SOUND_SAMPLE_RATE;
  uint32_t next = micros();

  for (uint32_t i = 0; i < HUM_SOUND_LENGTH; i++) {
    writeSample(HUM_SOUND[i]);
    next += periodUs;
    while ((int32_t)(micros() - next) < 0) { /* wait */ }
  }
}
```

For non-blocking playback, drive the sample step from a hardware timer interrupt instead of a busy-wait loop.

### Platform notes

- **ARM / ESP32 boards:** `const` arrays live in flash automatically, so no extra keywords are needed.
- **AVR boards (e.g. Uno/Nano):** RAM is very limited. You will need to add `PROGMEM` to the array declaration and read samples with `pgm_read_byte()`.
- The generated header uses `uint8_t`, so make sure `<stdint.h>` is included before the header (the Arduino core usually already does this).

## Troubleshooting

**`Unsupported sample width`**: 24-bit and floating-point WAV files are not supported. Re-export the file as standard 16-bit PCM WAV from Audacity or your DAW of choice.

**Audio sounds quiet**: Make sure normalization isn't disabled, then try a small `--gain` (e.g. `1.2`).

**Audio sounds distorted or crunchy**: Lower `--gain`. Also note that 8-bit audio at low sample rates has audible quantization noise. Try `--rate 11025` or `16000` if the result is too rough.

**Compile error on `uint8_t`**: Add `#include <stdint.h>` before including the generated header.

## How it works

1. Read the WAV and convert samples to floats in the range −1.0 to 1.0
2. Downmix to mono by averaging channels
3. Resample to the target rate using linear interpolation
4. Peak-normalize to 98% of full scale (unless `--no-normalize`)
5. Apply optional `--gain`, then clip to −1.0…1.0
6. Quantize to unsigned 8-bit (`round(x × 127 + 128)`) and write out as a C array

## Limitations

- Output is always mono, 8-bit unsigned PCM
- Resampling is linear interpolation with no anti-aliasing filter, which is fine for effects but not audiophile-grade. When downsampling from a high rate, content above half the target rate can alias
- Integer PCM input only (8/16/32-bit)

## License

MIT. See [LICENSE](LICENSE).

## Author

Made by [AW Labs](https://awlabs.carrd.co).
