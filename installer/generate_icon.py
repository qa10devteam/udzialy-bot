#!/usr/bin/env python3
"""
Generate icon.ico for Udzialy Bot installer.
Creates a simple 32x32 + 16x16 ICO with house + magnifying glass theme (blue/white).
Run: python3 generate_icon.py
"""
import struct
import os
import sys

# Add installer dir to path and import the generation logic
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def create_bitmap_data(size):
    """Create BGRA pixel data for the icon at given size."""
    pixels = bytearray(size * size * 4)
    BLUE = (0xCC, 0x88, 0x22, 0xFF)
    DARK_BLUE = (0xAA, 0x55, 0x11, 0xFF)
    WHITE = (0xFF, 0xFF, 0xFF, 0xFF)
    LIGHT_BLUE = (0xFF, 0xCC, 0x88, 0xFF)

    def set_pixel(x, y, color):
        if 0 <= x < size and 0 <= y < size:
            row = (size - 1 - y)
            offset = (row * size + x) * 4
            pixels[offset:offset+4] = bytes(color)

    def fill_rect(x1, y1, x2, y2, color):
        for yy in range(y1, y2):
            for xx in range(x1, x2):
                set_pixel(xx, yy, color)

    center = size // 2
    radius = size // 2 - 1
    for y in range(size):
        for x in range(size):
            if (x - center)**2 + (y - center)**2 <= radius**2:
                set_pixel(x, y, BLUE)

    if size == 32:
        for row in range(0, 8):
            for xx in range(4 + 8 - row, 4 + 8 + row + 1):
                set_pixel(xx, 6 + row, WHITE)
        fill_rect(5, 14, 19, 24, WHITE)
        fill_rect(10, 18, 14, 24, DARK_BLUE)
        fill_rect(6, 15, 9, 18, LIGHT_BLUE)
        fill_rect(15, 15, 18, 18, LIGHT_BLUE)
        for yy in range(8, 21):
            for xx in range(17, 30):
                if 16 <= (xx-23)**2 + (yy-14)**2 <= 36:
                    set_pixel(xx, yy, WHITE)
        for i in range(5):
            set_pixel(27+i, 19+i, WHITE)
            set_pixel(28+i, 19+i, WHITE)
    elif size == 16:
        for row in range(0, 4):
            for xx in range(1 + 4 - row, 1 + 4 + row + 1):
                set_pixel(xx, 2 + row, WHITE)
        fill_rect(2, 6, 9, 12, WHITE)
        fill_rect(4, 8, 7, 12, DARK_BLUE)
        for yy in range(4, 11):
            for xx in range(9, 16):
                if 4 <= (xx-12)**2 + (yy-7)**2 <= 9:
                    set_pixel(xx, yy, WHITE)
        set_pixel(14, 9, WHITE)
        set_pixel(15, 10, WHITE)

    return bytes(pixels)

def create_ico(filename):
    sizes = [32, 16]
    images = []
    for size in sizes:
        pixel_data = create_bitmap_data(size)
        and_mask_row_bytes = ((size + 31) // 32) * 4
        and_mask = bytes(and_mask_row_bytes * size)
        bmp_header = struct.pack('<IIIHHIIIIII',
            40, size, size * 2, 1, 32, 0,
            len(pixel_data) + len(and_mask), 0, 0, 0, 0)
        images.append((size, bmp_header + pixel_data + and_mask))

    icon_dir = struct.pack('<HHH', 0, 1, len(images))
    header_size = 6 + 16 * len(images)
    entries = b""
    data_blocks = b""
    offset = header_size
    for size, data in images:
        entries += struct.pack('<BBBBHHII', size, size, 0, 0, 1, 32, len(data), offset)
        data_blocks += data
        offset += len(data)

    with open(filename, 'wb') as f:
        f.write(icon_dir + entries + data_blocks)
    print(f"Created {filename} ({os.path.getsize(filename)} bytes)")

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    create_ico(os.path.join(script_dir, "icon.ico"))
