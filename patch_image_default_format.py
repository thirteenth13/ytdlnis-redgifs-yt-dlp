#!/usr/bin/env python3
from pathlib import Path
import sys

path = Path('yt_dlp/YoutubeDL.py')
text = path.read_text(encoding='utf-8')

old = '''    def _default_format_spec(self, info_dict):
        prefer_best = (
'''
new = '''    def _default_format_spec(self, info_dict):
        formats = self._get_formats(info_dict)
        if formats and all(f.get('vcodec') == 'images' for f in formats):
            return '*[vcodec=images]'

        prefer_best = (
'''

if "return '*[vcodec=images]'" not in text:
    if old not in text:
        print('ERROR: Could not locate YoutubeDL._default_format_spec', file=sys.stderr)
        sys.exit(1)
    text = text.replace(old, new, 1)
    path.write_text(text, encoding='utf-8')

# Strong verification: fail the build if the patch did not land.
check = path.read_text(encoding='utf-8')
if "return '*[vcodec=images]'" not in check:
    print('ERROR: image-only default format patch missing after write', file=sys.stderr)
    sys.exit(2)

print('Patched yt_dlp/YoutubeDL.py: image-only entries default to *[vcodec=images]')
