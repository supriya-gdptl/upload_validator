#!/usr/bin/env python3
"""
Generate sample_data/ test files for manual and automated testing.
Run once: python tests/generate_samples.py
"""

import os
import struct
import zlib

OUTPUT = os.path.join(os.path.dirname(__file__), "..", "sample_data")
os.makedirs(OUTPUT, exist_ok=True)


# ── PNG helper ────────────────────────────────────────────────────────────────

def make_png(filename: str, width: int, height: int, rgb: tuple):
    """Write a minimal solid-colour PNG."""
    def chunk(name, data):
        c = zlib.crc32(name + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + name + data + struct.pack(">I", c)

    raw = b""
    for _ in range(height):
        raw += b"\x00" + bytes(rgb) * width

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    idat = zlib.compress(raw)

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", idat)
        + chunk(b"IEND", b"")
    )
    path = os.path.join(OUTPUT, filename)
    with open(path, "wb") as f:
        f.write(png)
    print(f"  created {path}")


# ── PDF helper ────────────────────────────────────────────────────────────────

def make_pdf(filename: str, text: str):
    """Write a minimal single-page PDF with embedded text."""
    content = f"BT /F1 12 Tf 50 750 Td ({text}) Tj ET"
    content_bytes = content.encode()
    stream = f"<</Length {len(content_bytes)}>>\nstream\n".encode() + content_bytes + b"\nendstream"

    pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<</Type/Catalog /Pages 2 0 R>>\nendobj\n"
        b"2 0 obj\n<</Type/Pages /Kids [3 0 R] /Count 1>>\nendobj\n"
        b"3 0 obj\n<</Type/Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources <</Font <</F1 5 0 R>>>>>>\nendobj\n"
        b"4 0 obj\n" + stream + b"\nendobj\n"
        b"5 0 obj\n<</Type/Font /Subtype/Type1 /BaseFont/Helvetica>>\nendobj\n"
        b"xref\n0 6\n0000000000 65535 f \n"
        b"trailer\n<</Size 6 /Root 1 0 R>>\nstartxref\n0\n%%EOF\n"
    )
    path = os.path.join(OUTPUT, filename)
    with open(path, "wb") as f:
        f.write(pdf)
    print(f"  created {path}")


# ── Tiny MP4 helper ───────────────────────────────────────────────────────────

def make_mp4(filename: str):
    """Write a minimal (but structurally valid) MP4 stub."""
    # ftyp box — enough to be recognised as mp4
    ftyp = (
        b"\x00\x00\x00\x18"   # box size = 24
        b"ftyp"
        b"mp42"               # major brand
        b"\x00\x00\x00\x00"  # minor version
        b"mp42mp41"           # compatible brands
    )
    path = os.path.join(OUTPUT, filename)
    with open(path, "wb") as f:
        f.write(ftyp)
    print(f"  created {path}")


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Generating sample data…")

    # Images
    make_png("red_square.png",   200, 200, (220, 50,  50))   # "a red square image"
    make_png("blue_square.png",  200, 200, (50,  100, 220))  # "a blue square image"
    make_png("green_square.png", 200, 200, (50,  180, 80))   # "a green square image"

    # PDFs
    make_pdf("invoice.pdf",   "Invoice Number 12345 Total Amount Due 500 USD")
    make_pdf("contract.pdf",  "Service Agreement between Acme Corp and Client")
    make_pdf("recipe.pdf",    "Chocolate Cake Recipe Ingredients Flour Sugar Eggs")

    # MP4 stubs (won't decode real frames, but tests file routing)
    make_mp4("sample_video.mp4")

    print("\nDone. Files written to sample_data/")
    print("\nSuggested description matches:")
    print("  red_square.png   -> 'a red coloured square image'")
    print("  blue_square.png  -> 'a blue square illustration'")
    print("  invoice.pdf      -> 'an invoice with payment amount'")
    print("  contract.pdf     -> 'a service agreement document'")
    print("  recipe.pdf       -> 'chocolate cake recipe with ingredients'")
