"""VELMORA — entrypoint.

Renders the travel poster for VELMORA, a place that isn't there, and
writes it to /output/entry.png (1024x1024 PNG, <= 1 MiB).
Deterministic: seed 7, no network, no external assets.
"""

import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from render import render_poster


def main():
    out_dir = "/output"
    try:
        os.makedirs(out_dir, exist_ok=True)
        probe = os.path.join(out_dir, ".write_test")
        with open(probe, "w") as f:
            f.write("ok")
        os.remove(probe)
    except OSError:
        out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "output")
        os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "entry.png")

    img, info = render_poster()
    img.save(out_path, "PNG", optimize=True)

    with open(out_path, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    size = os.path.getsize(out_path)
    print(f"wrote {out_path} {img.size[0]}x{img.size[1]} {size} bytes")
    print(f"sha256 {digest}")
    print(f"font {info['font']} size {info['font_size']} "
          f"name {info['name_width']}x{info['name_height']} px")
    assert img.size == (1024, 1024), "entry must be 1024x1024"
    assert size <= 1048576, "entry must be <= 1 MiB"


if __name__ == "__main__":
    main()
