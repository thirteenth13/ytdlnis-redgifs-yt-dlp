#!/usr/bin/env python3
from pathlib import Path
import sys

path = Path("yt_dlp/extractor/tiktok.py")
text = path.read_text(encoding="utf-8")

old_default = '''        default = [''] if self._KNOWN_DEVICE_ID else []
        return self._configuration_arg('app_info', default, ie_key=TikTokIE)
'''
new_default = '''        default = [''] if self._KNOWN_DEVICE_ID else [
            '/musical_ly/35.1.3/2023501030/1233',
        ]
        return self._configuration_arg('app_info', default, ie_key=TikTokIE)
'''

if "musical_ly/35.1.3/2023501030/1233" not in text:
    if old_default not in text:
        print("ERROR: Could not locate _KNOWN_APP_INFO default block", file=sys.stderr)
        sys.exit(2)
    text = text.replace(old_default, new_default, 1)

helper_marker = "    def _solve_challenge_and_set_cookies(self, webpage):\n"
helper = '''    def _parse_aweme_slideshow_app(self, aweme_detail):
        # Return a playlist of slideshow images, or None for a normal video.
        aweme_id = aweme_detail.get('aweme_id')
        image_post = aweme_detail.get('image_post_info') or {}

        images = (
            image_post.get('images')
            or image_post.get('image_list')
            or aweme_detail.get('images')
            or []
        )
        if not isinstance(images, list) or not images:
            return None

        entries = []
        description = aweme_detail.get('desc') or 'TikTok slideshow'

        def first_image_url(image):
            candidates = (
                traverse_obj(image, ('download_url', 'url_list', ..., {url_or_none}))
                + traverse_obj(image, ('download_addr', 'url_list', ..., {url_or_none}))
                + traverse_obj(image, ('image_url', 'url_list', ..., {url_or_none}))
                + traverse_obj(image, ('display_image', 'url_list', ..., {url_or_none}))
                + traverse_obj(image, ('owner_watermark_image', 'url_list', ..., {url_or_none}))
                + traverse_obj(image, ('url_list', ..., {url_or_none}))
                + traverse_obj(image, ('download_url_list', ..., {url_or_none}))
            )
            return next((url for url in candidates if url), None)

        for index, image in enumerate(images, 1):
            if not isinstance(image, dict):
                continue
            image_url = first_image_url(image)
            if not image_url:
                continue
            ext = determine_ext(image_url, default_ext='jpg')
            entries.append({
                'id': f'{aweme_id}_{index:02d}',
                'title': f'{truncate_string(description, left=64)} [{index:02d}]',
                'url': image_url,
                'ext': ext,
                'vcodec': 'none',
                'acodec': 'none',
                'thumbnail': image_url,
                'http_headers': {'Referer': self._WEBPAGE_HOST},
            })

        if not entries:
            return None

        return self.playlist_result(
            entries,
            playlist_id=aweme_id,
            playlist_title=truncate_string(description, left=72),
        )

'''

if "_parse_aweme_slideshow_app" not in text:
    if helper_marker not in text:
        print("ERROR: Could not locate helper insertion marker", file=sys.stderr)
        sys.exit(3)
    text = text.replace(helper_marker, helper + helper_marker, 1)

old_extract = '''        if not aweme_detail:
            raise ExtractorError('Unable to extract aweme detail info', video_id=aweme_id)
        return self._parse_aweme_video_app(aweme_detail)
'''
new_extract = '''        if not aweme_detail:
            raise ExtractorError('Unable to extract aweme detail info', video_id=aweme_id)

        slideshow = self._parse_aweme_slideshow_app(aweme_detail)
        if slideshow:
            return slideshow

        return self._parse_aweme_video_app(aweme_detail)
'''

if "slideshow = self._parse_aweme_slideshow_app(aweme_detail)" not in text:
    if old_extract not in text:
        print("ERROR: Could not locate _extract_aweme_app return block", file=sys.stderr)
        sys.exit(4)
    text = text.replace(old_extract, new_extract, 1)

path.write_text(text, encoding="utf-8")
print(f"Patched {path}")
