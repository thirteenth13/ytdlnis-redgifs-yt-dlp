#!/usr/bin/env python3
from pathlib import Path
import runpy
import sys

# First normalize the custom TikTok slideshow child formats. yt-dlp's common-field
# processing treats image extensions as codec-less (vcodec=none, acodec=none), so
# selecting them with a vcodec=images filter does not work after sanitization.
tiktok_path = Path('yt_dlp/extractor/tiktok.py')
tiktok = tiktok_path.read_text(encoding='utf-8')
old_image_format = '''                    'format_id': '0',
                    'url': image_url,
                    'ext': ext,
                    'vcodec': 'images',
                    'acodec': 'none',
'''
new_image_format = '''                    'format_id': 'tiktok_image',
                    'url': image_url,
                    'ext': ext,
                    'vcodec': 'none',
                    'acodec': 'none',
'''
if old_image_format in tiktok:
    tiktok = tiktok.replace(old_image_format, new_image_format)
    tiktok_path.write_text(tiktok, encoding='utf-8')

if "'format_id': 'tiktok_image'" not in tiktok_path.read_text(encoding='utf-8'):
    print('ERROR: TikTok slideshow image format marker missing', file=sys.stderr)
    sys.exit(1)

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
        sys.exit(2)
    path.write_text(text, encoding='utf-8')

check = path.read_text(encoding='utf-8')
if "return 'tiktok_image'" not in check:
    print('ERROR: TikTok image default format patch missing after write', file=sys.stderr)
    sys.exit(3)

print("Patched TikTok slideshow images: exact format id 'tiktok_image' is selected by default")

# Keep the workflow stable: this script is already executed on every build, so use
# it as the integration point for the independent OnlyFans extractor patch.
onlyfans_patch = Path('../patch_onlyfans.py')
if onlyfans_patch.exists():
    runpy.run_path(str(onlyfans_patch), run_name='__main__')
    if not Path('yt_dlp/extractor/onlyfans.py').exists():
        print('ERROR: OnlyFans extractor was not created', file=sys.stderr)
        sys.exit(4)
else:
    print('ERROR: patch_onlyfans.py is missing', file=sys.stderr)
    sys.exit(4)
