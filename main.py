"""VELMORA — entrypoint (PURE STDLIB, no PIL / numpy / fonts).

Renders the travel poster for VELMORA, a place that isn't there, and
writes it to <output>/entry.png (1024x1024 PNG, <= 1 MiB).
Deterministic: seed 7, no network, no external assets.

Output dir: first writable of MAKEFUN_OUTPUT_DIR, /output, /tmp.
Never falls back to the repo dir (the grader mounts it read-only).
"""

import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from render import render_poster


def _pick_output_dir():
    candidates = []
    env_dir = os.environ.get("MAKEFUN_OUTPUT_DIR")
    if env_dir:
        candidates.append(env_dir)
    candidates += ["/output", "/tmp"]
    for d in candidates:
        try:
            os.makedirs(d, exist_ok=True)
            probe = os.path.join(d, ".write_test")
            with open(probe, "w") as f:
                f.write("ok")
            os.remove(probe)
            return d
        except OSError:
            continue
    raise RuntimeError("no writable output dir among: %r" % (candidates,))


def main():
    out_dir = _pick_output_dir()
    out_path = os.path.join(out_dir, "entry.png")

    png, info = render_poster()
    with open(out_path, "wb") as f:
        f.write(png)

    with open(out_path, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    size = os.path.getsize(out_path)
    print("wrote %s 1024x1024 %d bytes" % (out_path, size))
    print("sha256 %s" % digest)
    print("font %s name %dx%d px" % (info["font"], info["name_width"],
                                     info["name_height"]))
    assert size <= 1048576, "entry must be <= 1 MiB"
    # PNG header check: IHDR width/height must be 1024x1024.
    assert png[16:20] == b"\x00\x00\x04\x00", "PNG width must be 1024"
    assert png[20:24] == b"\x00\x00\x04\x00", "PNG height must be 1024"


if __name__ == "__main__":
    main()
