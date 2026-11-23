#!/usr/bin/env python3
"""Makes an own app's raster icons from its favicon.svg, beside it.

    scripts/app-icons.py <app>/apps/web/public/favicon.svg

Writes favicon.ico (16, 32 and 48), apple-touch-icon.png (180) and
icon-512.png. The drawing is done by Chrome, so the PNGs are the SVG exactly
as a browser shows it. Needs Google Chrome (or CHROME=<path>) and Pillow.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from PIL import Image

CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
SIZE = 1024


def main():
    if len(sys.argv) != 2 or not sys.argv[1].endswith(".svg"):
        sys.exit(__doc__)
    svg = Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory() as work:
        # A page of exactly the icon: Chrome's screenshot of a bare SVG adds a margin.
        page = Path(work) / "icon.html"
        page.write_text(f'<body style="margin:0;background:transparent"><img src="{svg.as_uri()}" width="{SIZE}" height="{SIZE}" style="display:block">')
        shot = Path(work) / "icon.png"
        subprocess.run([CHROME, "--headless", "--disable-gpu", "--hide-scrollbars", "--default-background-color=00000000",
                        f"--window-size={SIZE},{SIZE}", f"--screenshot={shot}", page.as_uri()],
                       check=True, capture_output=True, timeout=60)
        icon = Image.open(shot).convert("RGBA")
    if icon.size != (SIZE, SIZE):
        sys.exit(f"Chrome drew {icon.size}, expected {SIZE} square")
    for name, size in (("apple-touch-icon.png", 180), ("icon-512.png", 512)):
        icon.resize((size, size), Image.LANCZOS).save(svg.with_name(name), optimize=True)
    icon.save(svg.with_name("favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48)])
    print("wrote favicon.ico, apple-touch-icon.png and icon-512.png in", svg.parent)


if __name__ == "__main__":
    main()
