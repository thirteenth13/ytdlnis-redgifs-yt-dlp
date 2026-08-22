#!/usr/bin/env python3
from pathlib import Path
import sys

path = Path("yt_dlp/extractor/redgifs.py")
text = path.read_text(encoding="utf-8")
changed = False

# Large RedGifs user/search playlists can hit the API rate limit. Add a small
# page-to-page delay plus exponential backoff for HTTP 429 responses.
if 'import random\n' not in text or 'import time\n' not in text:
    old_imports = "import functools\nimport urllib.parse\n"
    new_imports = "import functools\nimport random\nimport time\nimport urllib.parse\n"
    if old_imports not in text:
        print("ERROR: Could not locate RedGifs import block.", file=sys.stderr)
        sys.exit(2)
    text = text.replace(old_imports, new_imports, 1)
    changed = True

old_call_api = '''    def _call_api(self, ep, video_id, **kwargs):
        for first_attempt in True, False:
            if 'authorization' not in self._API_HEADERS:
                self._fetch_oauth_token(video_id)
            try:
                headers = dict(self._API_HEADERS)
                headers['x-customheader'] = f'https://www.redgifs.com/watch/{video_id}'
                data = self._download_json(
                    f'https://api.redgifs.com/v2/{ep}', video_id, headers=headers, **kwargs)
                break
            except ExtractorError as e:
                if first_attempt and isinstance(e.cause, HTTPError) and e.cause.status == 401:
                    del self._API_HEADERS['authorization']  # refresh the token
                    continue
                raise
'''

new_call_api = '''    def _call_api(self, ep, video_id, **kwargs):
        auth_refreshed = False
        max_429_retries = 6
        for attempt in range(max_429_retries + 1):
            if 'authorization' not in self._API_HEADERS:
                self._fetch_oauth_token(video_id)
            try:
                headers = dict(self._API_HEADERS)
                headers['x-customheader'] = f'https://www.redgifs.com/watch/{video_id}'
                data = self._download_json(
                    f'https://api.redgifs.com/v2/{ep}', video_id, headers=headers, **kwargs)
                break
            except ExtractorError as e:
                if isinstance(e.cause, HTTPError) and e.cause.status == 401 and not auth_refreshed:
                    self._API_HEADERS.pop('authorization', None)  # refresh the token once
                    auth_refreshed = True
                    continue
                if isinstance(e.cause, HTTPError) and e.cause.status == 429 and attempt < max_429_retries:
                    retry_after = None
                    try:
                        retry_after = int(e.cause.response.headers.get('Retry-After') or 0)
                    except (AttributeError, TypeError, ValueError):
                        pass
                    # Respect Retry-After when supplied; otherwise use bounded
                    # exponential backoff with jitter: ~5, 10, 20, 40, 60, 60s.
                    delay = retry_after or min(60, 5 * (2 ** attempt))
                    delay += random.uniform(0.5, 2.0)
                    self.report_warning(
                        f'RedGifs API rate limit (HTTP 429); retrying in {delay:.1f}s '
                        f'({attempt + 1}/{max_429_retries})')
                    time.sleep(delay)
                    continue
                raise
'''

if 'RedGifs API rate limit (HTTP 429)' not in text:
    if old_call_api not in text:
        print("ERROR: Could not locate RedGifs _call_api block.", file=sys.stderr)
        print("Upstream redgifs.py probably changed; update patch_redgifs.py.", file=sys.stderr)
        sys.exit(3)
    text = text.replace(old_call_api, new_call_api, 1)
    changed = True

old_fetch_page = '''    def _fetch_page(self, ep, video_id, query, page):
        query['page'] = page + 1
        data = self._call_api(
            ep, video_id, query=query, note=f'Downloading JSON metadata page {page + 1}')

        for entry in data['gifs']:
            yield self._parse_gif_data(entry)
'''

new_fetch_page = '''    def _fetch_page(self, ep, video_id, query, page):
        query['page'] = page + 1
        # Pace large playlists proactively so Seal/YTDLnis do not hammer the
        # RedGifs metadata API while walking hundreds or thousands of items.
        if page:
            delay = random.uniform(1.0, 2.0)
            self.write_debug(f'RedGifs playlist pacing: sleeping {delay:.1f}s before page {page + 1}')
            time.sleep(delay)
        data = self._call_api(
            ep, video_id, query=query, note=f'Downloading JSON metadata page {page + 1}')

        for entry in data['gifs']:
            yield self._parse_gif_data(entry)
'''

if 'RedGifs playlist pacing:' not in text:
    if old_fetch_page not in text:
        print("ERROR: Could not locate RedGifs _fetch_page block.", file=sys.stderr)
        sys.exit(4)
    text = text.replace(old_fetch_page, new_fetch_page, 1)
    changed = True

# Keep the existing thumbnail enhancement used by the Android front-ends.
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

if "'thumbnail': (" not in text or "thumbs2.redgifs.com/{video_id}-poster.jpg" not in text:
    if needle not in text:
        print("ERROR: Could not locate expected RedGifs return block.", file=sys.stderr)
        print("Upstream redgifs.py probably changed; update patch_redgifs.py.", file=sys.stderr)
        sys.exit(5)
    text = text.replace(needle, replacement, 1)
    changed = True

if changed:
    path.write_text(text, encoding="utf-8")
    print(f"Patched {path}: thumbnails + large-playlist pacing + HTTP 429 backoff")
else:
    print("RedGifs patches already present")
