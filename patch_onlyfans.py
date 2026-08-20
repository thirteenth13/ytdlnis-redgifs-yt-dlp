#!/usr/bin/env python3
from pathlib import Path
import sys

path = Path('yt_dlp/extractor/onlyfans.py')
path.write_text(r'''import hashlib
import re
import time
from urllib.parse import urlencode, urlparse

from .common import InfoExtractor
from ..utils import ExtractorError, int_or_none, traverse_obj, url_or_none


class OnlyFansBaseIE(InfoExtractor):
    _RULES_URL = 'https://raw.githubusercontent.com/DATAHOARDERS/dynamic-rules/main/onlyfans.json'
    _API = 'https://onlyfans.com/api2/v2'
    _DEFAULT_UA = (
        'Mozilla/5.0 (Linux; Android 14; K) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36')
    _AUTO_X_BC = None

    def _auth_id(self):
        cookies = self._get_cookies('https://onlyfans.com/')
        auth_id = cookies.get('auth_id')
        sess = cookies.get('sess')
        if not auth_id or not sess:
            raise ExtractorError(
                'OnlyFans auth_id and sess cookies are required. Import cookies from a logged-in OnlyFans session',
                expected=True)
        return auth_id.value

    def _rules(self):
        rules = self._download_json(self._RULES_URL, None, note='Downloading current OnlyFans signing rules')
        required = ('static_param', 'format', 'checksum_indexes', 'checksum_constant', 'app_token')
        if not all(k in rules for k in required):
            raise ExtractorError('OnlyFans dynamic signing rules are incomplete', expected=True)
        return rules

    def _user_agent(self):
        values = self._configuration_arg('user_agent', ie_key='OnlyFans')
        if values and values[0]:
            return values[0]
        configured = self.get_param('http_headers') or {}
        return configured.get('User-Agent') or configured.get('user-agent') or self._DEFAULT_UA

    def _bootstrap_x_bc(self, video_id=None):
        if self._AUTO_X_BC:
            return self._AUTO_X_BC

        page_url = 'https://onlyfans.com/'
        if video_id and not str(video_id).isdigit():
            page_url = f'https://onlyfans.com/{video_id}'

        self.write_debug('Trying to auto-detect OnlyFans x-bc from authenticated browser page')
        try:
            webpage, handle = self._download_webpage_handle(
                page_url, str(video_id or 'onlyfans'),
                note='Bootstrapping OnlyFans browser session', fatal=False,
                headers={'User-Agent': self._user_agent()}, impersonate='chrome')
        except Exception as e:
            self.write_debug(f'OnlyFans x-bc bootstrap page failed: {e}')
            return None

        # Some deployments/proxies can expose it as a response header.
        if handle:
            headers = getattr(handle, 'headers', None) or {}
            for key in ('x-bc', 'X-BC', 'X-Bc'):
                try:
                    value = headers.get(key)
                except Exception:
                    value = None
                if value:
                    self._AUTO_X_BC = value
                    self.write_debug('Auto-detected OnlyFans x-bc from response headers')
                    return value

        if not webpage:
            return None

        # Best-effort extraction from server-rendered bootstrap state / inline JS.
        patterns = (
            r'["\']x-bc["\']\s*[:=]\s*["\']([^"\']{20,})',
            r'["\']x_bc["\']\s*[:=]\s*["\']([^"\']{20,})',
            r'\bx-bc\b\\?"?\s*[:=]\s*\\?["\']([^"\'\\\s]{20,})',
        )
        for pattern in patterns:
            match = re.search(pattern, webpage, flags=re.I)
            if match:
                value = match.group(1).replace('\\/', '/').replace('\\u002F', '/')
                self._AUTO_X_BC = value
                self.write_debug('Auto-detected OnlyFans x-bc from authenticated page bootstrap data')
                return value

        self.write_debug('Authenticated OnlyFans page did not expose x-bc in HTML/response headers')
        return None

    def _x_bc(self, video_id=None):
        values = self._configuration_arg('x_bc', ie_key='OnlyFans')
        if values and values[0]:
            return values[0]

        cookies = self._get_cookies('https://onlyfans.com/')
        for name in ('x-bc', 'x_bc'):
            cookie = cookies.get(name)
            if cookie and cookie.value:
                return cookie.value

        auto_value = self._bootstrap_x_bc(video_id)
        if auto_value:
            return auto_value

        raise ExtractorError(
            'OnlyFans x-bc is not present in cookies and was not exposed by the authenticated webpage. '
            'The browser normally generates/stores it outside the cookie jar. '
            'Pass it once with --extractor-args "onlyfans:x_bc=VALUE".', expected=True)

    def _signed_json(self, url, video_id, *, note=None, query=None):
        rules = self._rules()
        auth_id = self._auth_id()
        request_url = url
        if query:
            request_url = f'{url}?{urlencode(query)}'
        parsed = urlparse(request_url)
        signed_path = parsed.path + (f'?{parsed.query}' if parsed.query else '')

        timestamp = str(round(time.time() * 1000))
        message = '\n'.join((rules['static_param'], timestamp, signed_path, auth_id)).encode()
        sha1 = hashlib.sha1(message).hexdigest()
        checksum = sum(ord(sha1[i]) for i in rules['checksum_indexes']) + rules['checksum_constant']
        headers = {
            'Accept': 'application/json, text/plain, */*',
            'App-Token': rules['app_token'],
            'Referer': 'https://onlyfans.com/',
            'User-Agent': self._user_agent(),
            'User-Id': auth_id,
            'X-BC': self._x_bc(video_id),
            'Time': timestamp,
            'Sign': rules['format'].format(sha1, abs(checksum)),
        }
        for header in rules.get('remove_headers') or ():
            for key in tuple(headers):
                if key.lower() == header.lower():
                    headers.pop(key, None)

        self.write_debug(f'OnlyFans signed API path: {signed_path}')
        return self._download_json(
            request_url, video_id, note=note, headers=headers, impersonate='chrome')

    def _media_entries(self, post, username=None):
        post_id = str(post.get('id') or '')
        title = post.get('text') or post.get('rawText') or f'OnlyFans post {post_id}'
        author = post.get('author') or {}
        username = username or author.get('username')
        entries = []
        for idx, media in enumerate(post.get('media') or (), 1):
            media_type = media.get('type')
            url = traverse_obj(media, (
                ('source', ('files', 'full', 'url'), ('files', 'source', 'url'), 'url'),
                {url_or_none}, any))
            if not url:
                continue
            media_id = str(media.get('id') or f'{post_id}_{idx:02d}')
            entry = {
                'id': media_id,
                'title': title,
                'uploader': username,
                'uploader_id': str(author.get('id') or '') or None,
                'webpage_url': f'https://onlyfans.com/{post_id}/{username}' if username else None,
                'timestamp': int_or_none(post.get('postedAtPrecise')),
            }
            if media_type == 'video':
                entry.update({'url': url, 'ext': 'mp4'})
            else:
                entry.update({
                    'formats': [{'format_id': 'onlyfans_image', 'url': url, 'vcodec': 'none', 'acodec': 'none'}],
                    'ext': 'jpg',
                })
            entries.append(entry)
        return entries


class OnlyFansPostIE(OnlyFansBaseIE):
    IE_NAME = 'onlyfans:post'
    _VALID_URL = r'https?://(?:www\.)?onlyfans\.com/(?P<id>\d+)(?:/(?P<username>[\w.-]+))?/?(?:[?#].*)?$'

    def _real_extract(self, url):
        post_id, username = self._match_valid_url(url).group('id', 'username')
        post = self._signed_json(
            f'{self._API}/posts/{post_id}', post_id,
            note='Downloading OnlyFans post', query={'skip_users': 'all'})
        entries = self._media_entries(post, username)
        if not entries:
            if traverse_obj(post, ('media', ..., 'files', 'drm')):
                raise ExtractorError('This OnlyFans post contains DRM-protected media; DRM bypass is not supported', expected=True)
            raise ExtractorError('No downloadable non-DRM media found in this OnlyFans post', expected=True)
        return self.playlist_result(entries, post_id, post.get('text') or f'OnlyFans post {post_id}')


class OnlyFansUserIE(OnlyFansBaseIE):
    IE_NAME = 'onlyfans:user'
    _VALID_URL = r'https?://(?:www\.)?onlyfans\.com/(?P<id>(?!my(?:/|$)|api2(?:/|$))[\w.-]+)(?:/(?:videos|photos))?/?(?:[?#].*)?$'

    def _entries(self, user_id, username):
        after = None
        seen = set()
        while True:
            query = {
                'limit': 100, 'order': 'publish_date_asc', 'skip_users': 'all',
                'skip_users_dups': 1, 'pinned': 0, 'format': 'infinite',
            }
            if after is not None:
                query['afterPublishTime'] = after
            posts = self._signed_json(
                f'{self._API}/users/{user_id}/posts', username,
                note='Downloading OnlyFans timeline', query=query)
            if not isinstance(posts, list) or not posts:
                break
            new_posts = 0
            for post in posts:
                post_id = str(post.get('id') or '')
                if not post_id or post_id in seen:
                    continue
                seen.add(post_id)
                new_posts += 1
                yield from self._media_entries(post, username)
            if not new_posts or len(posts) < 100:
                break
            after = posts[-1].get('postedAtPrecise') or posts[-1].get('postedAt')
            if after is None:
                break

    def _real_extract(self, url):
        username = self._match_id(url)
        profile = self._signed_json(
            f'{self._API}/users/{username}', username, note='Downloading OnlyFans profile')
        user_id = profile.get('id')
        if not user_id:
            raise ExtractorError(f'Unable to resolve OnlyFans profile @{username}', expected=True)
        return self.playlist_result(self._entries(user_id, username), str(user_id), profile.get('name') or username)
''', encoding='utf-8')
print(f'Created {path}: OnlyFans profile/post extractor for authenticated non-DRM media')

registry = Path('yt_dlp/extractor/_extractors.py')
registry_text = registry.read_text(encoding='utf-8')
import_block = '''from .onlyfans import (\n    OnlyFansPostIE,\n    OnlyFansUserIE,\n)\n'''
if 'OnlyFansPostIE' not in registry_text:
    marker = 'from .ondemandkorea import OnDemandKoreaIE\n'
    if marker in registry_text:
        registry_text = registry_text.replace(marker, marker + import_block, 1)
    else:
        registry_text += '\n' + import_block
    registry.write_text(registry_text, encoding='utf-8')

check = registry.read_text(encoding='utf-8')
if 'OnlyFansPostIE' not in check or 'OnlyFansUserIE' not in check:
    print('ERROR: OnlyFans extractors were not registered in _extractors.py', file=sys.stderr)
    sys.exit(2)
print('Registered OnlyFansPostIE and OnlyFansUserIE in yt_dlp/extractor/_extractors.py')
