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
        aweme_id = aweme_detail.get('aweme_id')
        image_post = aweme_detail.get('image_post_info') or {}
        images = image_post.get('images') or image_post.get('image_list') or aweme_detail.get('images') or []
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
                'formats': [{
                    'format_id': '0',
                    'url': image_url,
                    'ext': ext,
                    'vcodec': 'images',
                    'acodec': 'none',
                    'http_headers': {'Referer': self._WEBPAGE_HOST},
                }],
                'thumbnail': image_url,
            })

        if not entries:
            return None
        return self.playlist_result(entries, playlist_id=aweme_id, playlist_title=truncate_string(description, left=72))

'''

if "_parse_aweme_slideshow_app" not in text:
    if helper_marker not in text:
        print("ERROR: Could not locate slideshow helper insertion marker", file=sys.stderr)
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

web_parser_marker = "    def _parse_aweme_video_web(self, aweme_detail, webpage_url, video_id, extract_flat=False):\n"
web_helper = '''    def _parse_aweme_slideshow_web(self, aweme_detail, webpage_url, video_id):
        image_post = (
            aweme_detail.get('imagePost')
            or aweme_detail.get('imagePostInfo')
            or aweme_detail.get('image_post_info')
            or {}
        )
        images = (
            image_post.get('images')
            or image_post.get('imageList')
            or image_post.get('image_list')
            or aweme_detail.get('images')
            or []
        )
        if not isinstance(images, list) or not images:
            return None

        description = aweme_detail.get('desc') or aweme_detail.get('description') or 'TikTok slideshow'
        entries = []

        def first_image_url(image):
            candidates = (
                traverse_obj(image, ('downloadUrl', 'urlList', ..., {url_or_none}))
                + traverse_obj(image, ('downloadURL', 'urlList', ..., {url_or_none}))
                + traverse_obj(image, ('imageURL', 'urlList', ..., {url_or_none}))
                + traverse_obj(image, ('imageUrl', 'urlList', ..., {url_or_none}))
                + traverse_obj(image, ('displayImage', 'urlList', ..., {url_or_none}))
                + traverse_obj(image, ('ownerWatermarkImage', 'urlList', ..., {url_or_none}))
                + traverse_obj(image, ('download_url', 'url_list', ..., {url_or_none}))
                + traverse_obj(image, ('image_url', 'url_list', ..., {url_or_none}))
                + traverse_obj(image, ('display_image', 'url_list', ..., {url_or_none}))
                + traverse_obj(image, ('urlList', ..., {url_or_none}))
                + traverse_obj(image, ('url_list', ..., {url_or_none}))
            )
            return next((url for url in candidates if url), None)

        for index, image in enumerate(images, 1):
            if not isinstance(image, dict):
                continue
            image_url = first_image_url(image)
            if not image_url:
                continue
            image_url = self._proto_relative_url(image_url)
            ext = determine_ext(image_url, default_ext='jpg')
            entries.append({
                'id': f'{video_id}_{index:02d}',
                'title': f'{truncate_string(description, left=64)} [{index:02d}]',
                'formats': [{
                    'format_id': '0',
                    'url': image_url,
                    'ext': ext,
                    'vcodec': 'images',
                    'acodec': 'none',
                    'http_headers': {'Referer': webpage_url},
                }],
                'thumbnail': image_url,
            })

        if not entries:
            return None
        return self.playlist_result(
            entries, playlist_id=video_id,
            playlist_title=truncate_string(description, left=72))

'''

if "def _parse_aweme_slideshow_web" not in text:
    if web_parser_marker not in text:
        print("ERROR: Could not locate web parser insertion marker", file=sys.stderr)
        sys.exit(7)
    text = text.replace(web_parser_marker, web_helper + web_parser_marker, 1)

old_web_start = '''    def _parse_aweme_video_web(self, aweme_detail, webpage_url, video_id, extract_flat=False):
        author_info = traverse_obj(aweme_detail, ((\'authorInfo\', \'author\', None), {
'''
new_web_start = '''    def _parse_aweme_video_web(self, aweme_detail, webpage_url, video_id, extract_flat=False):
        if not extract_flat:
            slideshow = self._parse_aweme_slideshow_web(aweme_detail, webpage_url, video_id)
            if slideshow:
                return slideshow

        author_info = traverse_obj(aweme_detail, ((\'authorInfo\', \'author\', None), {
'''

if "slideshow = self._parse_aweme_slideshow_web(aweme_detail, webpage_url, video_id)" not in text:
    if old_web_start not in text:
        print("ERROR: Could not locate _parse_aweme_video_web start block", file=sys.stderr)
        sys.exit(8)
    text = text.replace(old_web_start, new_web_start, 1)

user_marker = "    def _extract_sec_uid_from_embed(self, user_name):\n"
user_helpers = '''    def _extract_sec_uid_from_web_api(self, user_name):
        user_data = self._download_json(
            'https://www.tiktok.com/api/user/detail/', user_name,
            note='Resolving secondary user ID with TikTok web API',
            errnote='Unable to resolve secondary user ID with TikTok web API',
            fatal=False,
            headers=self._generate_blockbuster_headers(),
            query={
                'aid': '1988',
                'app_name': 'tiktok_web',
                'device_platform': 'web_pc',
                'uniqueId': user_name,
            }) or {}

        return traverse_obj(user_data, (
            ('userInfo', 'user_info', 'user'),
            ('user', None),
            ('secUid', 'sec_uid'), {str}, any))

    def _extract_sec_uid_from_app(self, user_name):
        try:
            user_data = self._call_api(
                'user/detail', user_name,
                query={'unique_id': user_name}, fatal=False,
                note='Resolving secondary user ID with Android API',
                errnote='Unable to resolve secondary user ID with Android API') or {}
        except ExtractorError as e:
            self.report_warning(f'Android API user lookup failed: {e}')
            return None

        return traverse_obj(user_data, (
            ('user', 'user_info', 'userInfo'),
            ('sec_uid', 'secUid'), {str}, any))

'''

if "def _extract_sec_uid_from_web_api" not in text:
    if user_marker not in text:
        print("ERROR: Could not locate TikTokUserIE secUid insertion marker", file=sys.stderr)
        sys.exit(5)
    text = text.replace(user_marker, user_helpers + user_marker, 1)

old_fallback = '''            else:
                sec_uid = self._extract_sec_uid_from_embed(user_name)
                fail_early = False
'''
new_fallback = '''            else:
                sec_uid = self._extract_sec_uid_from_web_api(user_name)
                if not sec_uid:
                    sec_uid = self._extract_sec_uid_from_app(user_name)
                if not sec_uid:
                    sec_uid = self._extract_sec_uid_from_embed(user_name)
                fail_early = False
'''

if "sec_uid = self._extract_sec_uid_from_web_api(user_name)" not in text:
    if old_fallback not in text:
        print("ERROR: Could not locate TikTokUserIE fallback block", file=sys.stderr)
        sys.exit(6)
    text = text.replace(old_fallback, new_fallback, 1)

path.write_text(text, encoding="utf-8")
print(f"Patched {path}")

# yt-dlp deliberately excludes image-only formats from its normal default selector.
# For image-only entries (such as our TikTok slideshow children), choose the image
# format automatically. Normal video/audio entries retain upstream selection.
ydl_path = Path("yt_dlp/YoutubeDL.py")
ydl = ydl_path.read_text(encoding="utf-8")
old_fmt = '''    def _default_format_spec(self, info_dict):
        prefer_best = (
'''
new_fmt = '''    def _default_format_spec(self, info_dict):
        formats = self._get_formats(info_dict)
        if formats and all(f.get('vcodec') == 'images' for f in formats):
            return '*[vcodec=images]'

        prefer_best = (
'''
if "all(f.get('vcodec') == 'images' for f in formats)" not in ydl:
    if old_fmt not in ydl:
        print("ERROR: Could not locate YoutubeDL._default_format_spec", file=sys.stderr)
        sys.exit(9)
    ydl = ydl.replace(old_fmt, new_fmt, 1)
    ydl_path.write_text(ydl, encoding="utf-8")
    print(f"Patched {ydl_path}")

print("TikTok: videos unchanged; slideshow entries expose real image formats and auto-select images by default")
