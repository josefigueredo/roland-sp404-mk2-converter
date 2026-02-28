# RolandConverter

Prepare WAV samples for the **Roland SP-404 MkII** drum sampler. Converts, organizes, and renames your sample libraries so they're ready to drop onto the SD card.

**What it does:**

- Scans your WAV library (thousands of files) and picks the best samples
- Converts to 16-bit / 48kHz mono (the SP-404 MkII native format)
- Trims silence from the start and end of each sample
- Renames files to short UPPERCASE names that fit the SP-404's small screen
- Organizes by instrument type: `KICKS/`, `SNARES/`, `HIHATS/`, `TOMS/`, etc.
- Generates an audit log so you can trace every output file back to its original
- **Never modifies your original files** -- only reads them

---

## Requirements

- **Windows 10/11** (tested), macOS/Linux should also work
- **Python 3.12** or newer
- **uv** -- a fast Python package manager

### Installing Python

If you don't have Python installed:

1. Go to https://www.python.org/downloads/
2. Download Python 3.12 or newer
3. Run the installer -- **check "Add Python to PATH"** during installation

### Installing uv

Open a terminal (PowerShell or Command Prompt) and run:

```
pip install uv
```

---

## Installation

1. **Download or clone this project**

   Click the green **Code** button on GitHub, then **Download ZIP**. Extract it somewhere, for example `C:\RolandConverter`.

   Or if you have Git:
   ```
   git clone https://github.com/YOUR_USERNAME/RolandConverter.git
   ```

2. **Open a terminal** in the project folder

   Navigate to where you extracted it:
   ```
   cd C:\RolandConverter
   ```

3. **Install dependencies**

   ```
   uv sync
   ```
   This creates a virtual environment and installs everything automatically.

---

## Usage

RolandConverter has two modes:

### Mode 1: Sounds From Mars library

If you have the **Sounds From Mars** sample packs:

#### See what packs are available

```
uv run roland-converter list-packs
```

#### Preview a specific pack (no files written)

```
uv run roland-converter preview "808 From Mars"
```

#### Convert with a dry run first (recommended)

```
uv run roland-converter convert -t 1 --dry-run -o "E:\Music\ROLAND"
```

This shows you what *would* happen without writing any files. The `-t 1` means tier 1 packs only (808, 909, MPC60, Junos).

#### Run the actual conversion

```
uv run roland-converter convert -t 1 -o "E:\Music\ROLAND"
```

To convert all tiers:
```
uv run roland-converter convert -t 1,2,3 -o "E:\Music\ROLAND"
```

### Mode 2: Any WAV folder (generic)

For **any** WAV sample library (YurtRock, custom samples, downloaded packs, etc.):

#### Preview what would be selected

```
uv run roland-converter preview-dir "E:\Music\YurtRock"
```

#### Convert with a dry run first

```
uv run roland-converter convert-dir "E:\Music\YurtRock" -o "E:\Music\ROLAND" --dry-run
```

#### Run the actual conversion

```
uv run roland-converter convert-dir "E:\Music\YurtRock" -o "E:\Music\ROLAND"
```

The generic mode detects instrument types from filenames (Kick, Snare, HiHat, Tom, Crash, Clap, etc.) and organizes them into the same folder structure.

---

## Loading onto the SP-404 MkII

1. Remove the SD card from your SP-404 MkII
2. Insert it into your computer
3. Copy the output folders (e.g. `E:\Music\ROLAND\KICKS\`, `SNARES\`, etc.) into the `ROLAND/IMPORT/` folder on the SD card
4. Put the SD card back in the SP-404
5. On the SP-404, go to **IMPORT** and load the samples

---

## Options Reference

| Option | Description |
|---|---|
| `-o`, `--target` | Output directory (where converted files go) |
| `-n`, `--dry-run` | Preview only, don't write any files |
| `-t`, `--tiers` | Which tiers to include: `1`, `1,2`, or `1,2,3` (From Mars mode) |
| `-p`, `--packs` | Specific pack names instead of tiers (From Mars mode) |
| `--max-per-folder` | Max samples per category folder (default: 30) |

---

## Output Structure

```
ROLAND/
  KICKS/
    808/
      BD_A_DK_A_01.WAV
      BD_A_DK_B_01.WAV
    909/
      BD_A_DK_A_01.WAV
  SNARES/
    808/
      SN_A_01.WAV
    909/
      SN_A_01.WAV
  HIHATS/
    CLOSED/
      808/
        CH_A.WAV
    OPEN/
      808/
        OH_COMBO.WAV
  TOMS/
  CLAPS/
  CYMBALS/
  PERCUSSION/
  audit_20260228_193000.md   <-- maps every file back to its original
```

---

## Audit Log

Every conversion generates a Markdown file (`audit_YYYYMMDD_HHMMSS.md`) in the output directory. It contains:

- A summary of how many files were scanned, selected, converted, and skipped
- A table mapping every original file path to its output path
- Audio details: sample rate, bit depth, duration, how much silence was trimmed
- Any errors that occurred

---

## Troubleshooting

**"roland-converter" is not recognized**
- Make sure you're in the project directory and using `uv run roland-converter`

**No WAV files found**
- Check that your source path is correct
- The From Mars packs need a specific folder structure -- use `list-packs` to check which packs are detected

**Files are skipped as "silent"**
- The tool skips files that are entirely below -60dB. These are usually empty placeholder files.

---

## License

MIT
