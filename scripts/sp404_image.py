"""Convert any PNG/JPG image to SP-404 MkII startup/screensaver BMP format.

Output: 128x64 monochrome BMP, best-fit aspect ratio with letterboxing.

Usage:
    uv run python scripts/sp404_image.py <input> <output.bmp> [options]

Examples:
    uv run python scripts/sp404_image.py logo.png startup_1.bmp
    uv run python scripts/sp404_image.py photo.jpg screen_saver_1.bmp --invert
    uv run python scripts/sp404_image.py art.png startup_2.bmp --threshold 100 --no-dither
"""

import argparse
import struct
import sys
from pathlib import Path

import numpy as np

TARGET_W = 128
TARGET_H = 64


def load_image(path: Path) -> np.ndarray:
    """Load an image file and return as RGB numpy array (H, W, 3)."""
    # Try Pillow first for broad format support
    try:
        from PIL import Image
        img = Image.open(path).convert("RGB")
        return np.array(img)
    except ImportError:
        pass

    # Fallback: try to read with basic decoders
    raise SystemExit(
        "Pillow is required: uv pip install Pillow"
    )


def fit_and_letterbox(img: np.ndarray, target_w: int, target_h: int) -> np.ndarray:
    """Resize image to fit target dimensions, letterboxing with black."""
    h, w = img.shape[:2]
    src_aspect = w / h
    dst_aspect = target_w / target_h

    if src_aspect > dst_aspect:
        # Source is wider: fit to width, letterbox top/bottom
        new_w = target_w
        new_h = max(1, int(target_w / src_aspect))
    else:
        # Source is taller: fit to height, letterbox left/right
        new_h = target_h
        new_w = max(1, int(target_h * src_aspect))

    # Resize using nearest-neighbor (good for pixel art / small targets)
    from PIL import Image
    pil_img = Image.fromarray(img)
    pil_img = pil_img.resize((new_w, new_h), Image.LANCZOS)
    resized = np.array(pil_img)

    # Create black canvas and center the image
    canvas = np.zeros((target_h, target_w, 3), dtype=np.uint8)
    y_off = (target_h - new_h) // 2
    x_off = (target_w - new_w) // 2
    canvas[y_off:y_off + new_h, x_off:x_off + new_w] = resized

    return canvas


def to_grayscale(img: np.ndarray) -> np.ndarray:
    """Convert RGB to grayscale using ITU-R BT.601 weights."""
    r, g, b = img[:, :, 0], img[:, :, 1], img[:, :, 2]
    return (0.299 * r + 0.587 * g + 0.114 * b).astype(np.uint8)


def floyd_steinberg_dither(gray: np.ndarray, threshold: int = 128) -> np.ndarray:
    """Apply Floyd-Steinberg dithering to a grayscale image. Returns 0/255 array."""
    h, w = gray.shape
    img = gray.astype(np.float32)

    for y in range(h):
        for x in range(w):
            old = img[y, x]
            new = 255.0 if old >= threshold else 0.0
            img[y, x] = new
            err = old - new

            if x + 1 < w:
                img[y, x + 1] += err * 7 / 16
            if y + 1 < h:
                if x > 0:
                    img[y + 1, x - 1] += err * 3 / 16
                img[y + 1, x] += err * 5 / 16
                if x + 1 < w:
                    img[y + 1, x + 1] += err * 1 / 16

    return np.clip(img, 0, 255).astype(np.uint8)


def threshold_convert(gray: np.ndarray, threshold: int = 128) -> np.ndarray:
    """Simple threshold: above = white (255), below = black (0)."""
    return np.where(gray >= threshold, np.uint8(255), np.uint8(0))


def write_1bit_bmp(pixels: np.ndarray, output_path: Path) -> None:
    """Write a 128x64 black/white image as a 1-bit BMP file.

    pixels: 2D uint8 array (H, W), values 0 (black) or 255 (white).
    BMP stores rows bottom-to-top, each row padded to 4-byte boundary.
    """
    h, w = pixels.shape
    assert w == TARGET_W and h == TARGET_H

    # 1-bit: 8 pixels per byte, rows padded to 4 bytes
    row_bytes = (w + 7) // 8  # 128/8 = 16
    row_padded = (row_bytes + 3) & ~3  # 16 is already 4-byte aligned

    # Color palette: 2 entries (black, white), 4 bytes each (B, G, R, 0)
    palette = b'\x00\x00\x00\x00' + b'\xff\xff\xff\x00'

    pixel_data_size = row_padded * h
    header_size = 14  # BITMAPFILEHEADER
    dib_size = 40     # BITMAPINFOHEADER
    palette_size = 8  # 2 colors * 4 bytes
    offset = header_size + dib_size + palette_size
    file_size = offset + pixel_data_size

    # BITMAPFILEHEADER (14 bytes)
    file_header = struct.pack('<2sIHHI',
        b'BM',         # signature
        file_size,     # file size
        0,             # reserved
        0,             # reserved
        offset,        # pixel data offset
    )

    # BITMAPINFOHEADER (40 bytes)
    dib_header = struct.pack('<IiiHHIIiiII',
        dib_size,      # header size
        w,             # width
        h,             # height (positive = bottom-up)
        1,             # color planes
        1,             # bits per pixel
        0,             # compression (BI_RGB)
        pixel_data_size,
        2835,          # h resolution (72 DPI in pixels/meter)
        2835,          # v resolution
        2,             # colors in palette
        2,             # important colors
    )

    # Pixel data: bottom row first, each pixel is 1 bit (MSB first)
    pixel_data = bytearray()
    for y in range(h - 1, -1, -1):  # bottom-to-top
        row = bytearray(row_padded)
        for x in range(w):
            if pixels[y, x] > 0:  # white pixel
                byte_idx = x // 8
                bit_idx = 7 - (x % 8)
                row[byte_idx] |= (1 << bit_idx)
        pixel_data.extend(row)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'wb') as f:
        f.write(file_header)
        f.write(dib_header)
        f.write(palette)
        f.write(bytes(pixel_data))


def convert_image(
    input_path: Path,
    output_path: Path,
    threshold: int = 128,
    dither: bool = True,
    invert: bool = False,
) -> None:
    """Convert any image to SP-404 MkII 128x64 monochrome BMP."""
    img = load_image(input_path)
    img = fit_and_letterbox(img, TARGET_W, TARGET_H)
    gray = to_grayscale(img)

    if dither:
        mono = floyd_steinberg_dither(gray, threshold)
    else:
        mono = threshold_convert(gray, threshold)

    if invert:
        mono = 255 - mono

    write_1bit_bmp(mono, output_path)

    size = output_path.stat().st_size
    print(f"Converted: {input_path.name} -> {output_path.name} ({size} bytes, 128x64 1-bit BMP)")


def main():
    parser = argparse.ArgumentParser(
        description="Convert PNG/JPG to SP-404 MkII startup/screensaver BMP (128x64, monochrome)",
    )
    parser.add_argument("input", type=Path, help="Input image (PNG, JPG, etc.)")
    parser.add_argument("output", type=Path, help="Output BMP (e.g., startup_1.bmp, screen_saver_1.bmp)")
    parser.add_argument("--threshold", type=int, default=128,
                        help="Black/white threshold 0-255 (default: 128)")
    parser.add_argument("--no-dither", action="store_true",
                        help="Disable Floyd-Steinberg dithering (use hard threshold)")
    parser.add_argument("--invert", action="store_true",
                        help="Invert colors (useful if source is dark-on-light)")

    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: {args.input} not found", file=sys.stderr)
        sys.exit(1)

    convert_image(
        input_path=args.input,
        output_path=args.output,
        threshold=args.threshold,
        dither=not args.no_dither,
        invert=args.invert,
    )


if __name__ == "__main__":
    main()
