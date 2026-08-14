#!/usr/bin/env python3
from pathlib import Path
import sys

path = Path("yt_dlp/extractor/redgifs.py")
text = path.read_text(encoding="utf-8")

needle = """            'age_limit': 18,
            'formats': formats,
"""

replacement = """            'age_limit': 18,
            'thumbnail': (
                (gif_data.get('urls') or {}).get('poster')
                or (gif_data.get('urls') or {}).get('thumbnail')
                or gif_data.get('poster')
                or gif_data.get('thumbnail')
                or gif_data.get('posterUrl')
                or gif_data.get('thumbnailUrl')
                or gif_data.get('mobilePosterUrl')
                or (
                    f'https://thumbs2.redgifs.com/{video_id}-poster.jpg'
                    if video_id else None
                )
            ),
            'formats': formats,
"""

if "'thumbnail': (" in text and "thumbs2.redgifs.com/{video_id}-poster.jpg" in text:
    print("RedGifs thumbnail patch already present")
    sys.exit(0)

if needle not in text:
    print("ERROR: Could not locate expected RedGifs return block.", file=sys.stderr)
    print("Upstream redgifs.py probably changed; update patch_redgifs.py.", file=sys.stderr)
    sys.exit(2)

path.write_text(text.replace(needle, replacement, 1), encoding="utf-8")
print(f"Patched {path}")
