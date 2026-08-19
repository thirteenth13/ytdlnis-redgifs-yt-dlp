#!/usr/bin/env python3
from pathlib import Path
import sys

path = Path('yt_dlp/YoutubeDL.py')
text = path.read_text(encoding='utf-8')

old = '''    def _default_format_spec(self, info_dict):
        prefer_best = (
'''
old_previous_patch = '''    def _default_format_spec(self, info_dict):
        formats = self._get_formats(info_dict)
        if formats and all(f.get('vcodec') == 'images' for f in formats):
            return '*[vcodec=images]'

        prefer_best = (
'''
new = '''    def _default_format_spec(self, info_dict):
        formats = self._get_formats(info_dict)
        if formats and any(f.get('format_id') == 'tiktok_image' for f in formats):
            return 'tiktok_image'

        prefer_best = (
'''

if "return 'tiktok_image'" not in text:
    if old_previous_patch in text:
        text = text.replace(old_previous_patch, new, 1)
    elif old in text:
        text = text.replace(old, new, 1)
    else:
        print('ERROR: Could not locate YoutubeDL._default_format_spec', file=sys.stderr)
        sys.exit(1)
    path.write_text(text, encoding='utf-8')

check = path.read_text(encoding='utf-8')
if "return 'tiktok_image'" not in check:
    print('ERROR: TikTok image default format patch missing after write', file=sys.stderr)
    sys.exit(2)

print("Patched yt_dlp/YoutubeDL.py: TikTok slideshow entries default to exact format id 'tiktok_image'")
