# Roland SP-404 MkII - Technical Reference

Quick reference for WAV sample preparation and SD card import.

---

## Audio Format Support

| Property                  | Value                                                         |
| ------------------------- | ------------------------------------------------------------- |
| **Formats (SD import)**   | WAV, AIFF, MP3                                                |
| **Formats (App/USB)**     | WAV, AIFF, MP3, FLAC, M4A (Mac only)                          |
| **Native sample rate**    | 48 kHz (fixed)                                                |
| **Accepted sample rates** | 44.1 kHz, 48 kHz, 96 kHz (auto-converted to 48 kHz on import) |
| **Internal bit depth**    | 16-bit linear PCM                                             |
| **Accepted bit depths**   | 16-bit, 24-bit (auto-downconverted to 16-bit)                 |
| **32-bit float**          | NOT supported                                                 |
| **Mono/Stereo**           | Both supported                                                |
| **WAV encoding**          | PCM only (no ADPCM or compressed WAV)                         |

**Key takeaway:** Pre-convert to **16-bit / 48 kHz** before import to avoid the device's internal resampling and preserve quality.

---

## Sample Limits

| Property                  | Value                                     |
| ------------------------- | ----------------------------------------- |
| **Max file size**         | 185,506,412 bytes (~185.5 MB)             |
| **Max duration (stereo)** | ~16 minutes                               |
| **Max duration (mono)**   | ~32 minutes                               |
| **Min duration**          | 100 ms (shorter files may fail to import) |

---

## Pads, Banks & Projects

| Property                | Value                     |
| ----------------------- | ------------------------- |
| **Pads per bank**       | 16 + 1 SUB pad            |
| **Banks**               | 10 (A through J)          |
| **Samples per project** | 160 (16 pads x 10 banks)  |
| **Total projects**      | 16                        |
| **Max total samples**   | 2,560 (160 x 16 projects) |

---

## Polyphony

| Property                   | Value                          |
| -------------------------- | ------------------------------ |
| **Max polyphony**          | 32 voices                      |
| **Stereo sample**          | Uses 2 voices                  |
| **Mono sample**            | Uses 1 voice                   |
| **Practical max (stereo)** | 16 simultaneous stereo samples |

**Implication:** Converting loops to mono doubles effective polyphony, but loses stereo width.

---

## SD Card

| Property            | Value                                                      |
| ------------------- | ---------------------------------------------------------- |
| **Card types**      | SDHC, SDXC                                                 |
| **Max capacity**    | 1 TB (confirmed)                                           |
| **Required format** | FAT32                                                      |
| **Format method**   | Always format on the SP-404 MkII itself, never on computer |

---

## Import Workflow

1. Remove SD card from SP-404 MkII
2. Insert into computer
3. Copy WAV files to the `IMPORT` folder on the SD card
4. Subfolders inside `IMPORT/` are supported and displayed on device
5. Put SD card back in SP-404 MkII
6. On device: hold **SHIFT** + press **pad 14** → _Import from SD-CARD_ → _SAMPLE_
7. Select files/folders to import, assign to pads

**Pad assignment on import:**

- Files go to first available empty pad slot, or user-selected pad
- If pad is occupied: Overwrite, Swap, or Cancel options

---

## Display & Naming

| Property               | Value                                               |
| ---------------------- | --------------------------------------------------- |
| **Display characters** | ~16 characters                                      |
| **Character support**  | ASCII alphanumeric + basic punctuation              |
| **Double-byte chars**  | May not display correctly                           |
| **Truncation**         | Names longer than ~16 chars are truncated on screen |

**Best practice:** Keep filenames to 20 characters max (excluding `.WAV`), UPPERCASE, no spaces.

---

## Internal Processing

- **Playback:** 48 kHz fixed
- **Processing bit depth:** 24-bit internal (for effects/mixing)
- **Storage bit depth:** 16-bit
- **Pitch shifting:** Repitch algorithm, not sample rate change
- **Metadata:** WAV headers, ID3 tags, cue points, regions are all discarded on import

---

## Optimal Format for RolandConverter

Based on the above specs, our target conversion format:

```
Sample rate:  48,000 Hz
Bit depth:    16-bit (PCM_16)
Channels:     Mono (drums/one-shots) or Stereo (loops/ambience)
Filename:     Max 20 chars, UPPERCASE, underscores
Extension:    .WAV
```

This matches the device's internal storage format exactly, avoiding quality loss from the device's own resampling.

---

## Custom Startup & Screensaver Images

The SP-404 MkII has a graphic OLED display that supports custom startup logos and screensaver images.

### Image Specifications

| Property         | Value                                                   |
| ---------------- | ------------------------------------------------------- |
| **Format**       | BMP (1-bit, 4-bit, 8-bit, or 24-bit accepted)           |
| **Resolution**   | 128 x 64 pixels                                         |
| **Aspect ratio** | 2:1 (width:height)                                      |
| **Display**      | Monochrome OLED (only black & white rendered, no grays) |
| **Background**   | Set to black (white logo on black background)           |

### File Naming (strict, device ignores other names)

| Type                   | Filenames                                          | Max per project |
| ---------------------- | -------------------------------------------------- | --------------- |
| **Startup images**     | `startup_1.bmp`, `startup_2.bmp`                   | 2               |
| **Screensaver images** | `screen_saver_1.bmp` through `screen_saver_16.bmp` | 16              |

### SD Card Path

```
SD-CARD/ROLAND/EXPORT/PROJECT/PROJECT_XX/PICTURE/
```

Where `XX` is the project number (01-16).

### Import Workflow

1. On the SP-404 MkII: **SHIFT + pad 14** → _Export Project_ → select project → exports to SD card
2. Remove SD card, insert in computer
3. Place `.bmp` files in the `PICTURE` folder of the exported project
4. Put SD card back in SP-404 MkII
5. **SHIFT + pad 14** → _Import Project_ → select project
6. Enable custom screensaver: **SHIFT + pad 13** (Utility) → SYSTEM → _Scrn Saver Type_ → Custom

### Image Converter

Use `scripts/sp404_image.py` to convert any PNG/JPG to the correct BMP format:

```
uv run python scripts/sp404_image.py photo.png startup_1.bmp
uv run python scripts/sp404_image.py logo.jpg screen_saver_1.bmp --invert
uv run python scripts/sp404_image.py art.png startup_1.bmp --threshold 100 --no-dither
```

---

## Sources

- [SP-404MK2: Audio file formats that can be imported](https://support.roland.com/hc/en-us/articles/4408190553883)
- [SP-404MK2: Maximum Sampling Time](https://support.roland.com/hc/en-us/articles/4408196941851)
- [SP-404MK2: SD Card Compatibility](https://support.roland.com/hc/en-us/articles/4408066121243)
- [SP-404MK2: Setting the Panning for a Sample](https://support.roland.com/hc/en-us/articles/4408196940187)
- [SP-404MK2: Formatting an SD Card](https://support.roland.com/hc/en-us/articles/24692189759899)
- [SP-404MK2 Reference Manual (v2.00)](https://static.roland.com/assets/media/pdf/SP-404mk2_reference_v200_eng04_W.pdf)
- [SP-404MK2 Importing Samples](https://static.roland.com/manuals/sp-404mk2_reference_v4/en-US/7958977178537867.html)
- [Converting WAV files for the SP404 MK2 - Seb Patron](https://sebpatron.com/sp404mk2-wav-converter/)
- [Working with Projects and Samples - Sweetwater](https://www.sweetwater.com/sweetcare/articles/working-with-projects-and-samples-on-the-roland-sp-404mkii/)
- [Ultimate Guide: Customizing the SP-404MKII - Roland Articles](https://articles.roland.com/ultimate-guide-customizing-the-sp-404-mkii/)
- [SP-404MK2 Customizing the Opening Screen](https://static.roland.com/manuals/sp-404mk2_reference_v4/en-US/7947559578523275.html)
- [Preparing a Screen Saver Image](https://static.roland.com/manuals/sp-404mk2_reference/eng/17805336.html)
- [SP-404 MK2 Screen Customizer Tool](https://alei1180.github.io/sp-404mk2-screen-customizer/)
