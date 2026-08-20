#!/usr/bin/env python3
from pathlib import Path

path = Path('yt_dlp/extractor/onlyfans.py')
path.write_text(r'''import hashlib
import time
from urllib.parse import urlparse

from .common import InfoExtractor
from ..utils import ExtractorError, int_or_none, traverse_obj, url_or_none


class OnlyFansBaseIE(InfoExtractor):
    _RULES_URL = 'https://raw.githubusercontent.com/DATAHOARDERS/dynamic-rules/main/onlyfans.json'
    _API = 'https://onlyfans.com/api2/v2'

    def _auth_id(self):
        cookies = self._get_cookies('https://onlyfans.com/')
        auth_id = cookies.get('auth_id')
        if not auth_id:
            raise ExtractorError(
                'OnlyFans login cookies are required. Import cookies from a logged-in OnlyFans session', expected=True)
        return auth_id.value

    def _rules(self):
        rules = self._download_json(self._RULES_URL, None, note='Downloading current OnlyFans signing rules')
        required = ('static_param', 'format', 'checksum_indexes', 'checksum_constant', 'app_token')
        if not all(k in rules for k in required):
            raise ExtractorError('OnlyFans dynamic signing rules are incomplete', expected=True)
        return rules

    def _signed_json(self, url, video_id, *, note=None, query=None):
        rules = self._rules()
        auth_id = self._auth_id()
        if query:
            from urllib.parse import urlencode
            sign_url = f'{url}?{urlencode(query)}'
        else:
            sign_url = url
        parsed = urlparse(sign_url)
        path = parsed.path + (f'?{parsed.query}' if parsed.query else '')
        timestamp = str(round(time.time() * 1000))
        message = '\n'.join((rules['static_param'], timestamp, path, auth_id)).encode()
        sha1 = hashlib.sha1(message).hexdigest()
        checksum = sum(ord(sha1[i]) for i in rules['checksum_indexes']) + rules['checksum_constant']
        headers = {
            'Accept': 'application/json, text/plain, */*',
            'App-Token': rules['app_token'],
            'Referer': 'https://onlyfans.com/',
            'User-Id': auth_id,
            'Time': timestamp,
            'Sign': rules['format'].format(sha1, abs(checksum)),
        }
        for header in rules.get('remove_headers') or ():
            headers.pop(header, None)
            headers.pop(header.title(), None)
        return self._download_json(url, video_id, note=note, query=query, headers=headers, impersonate=True)

    def _media_entries(self, post, username=None):
        post_id = str(post.get('id') or '')
        title = post.get('text') or post.get('rawText') or f'OnlyFans post {post_id}'
        author = post.get('author') or {}
        username = username or author.get('username')
        entries = []
        for idx, media in enumerate(post.get('media') or (), 1):
            media_type = media.get('type')
            files = media.get('files') or {}
            # Only expose direct non-DRM files. DRM manifests/licenses are intentionally unsupported.
            url = traverse_obj(media, (
                ('source', ('files', 'full', 'url'), ('files', 'source', 'url'), 'url'),
                {url_or_none}, any))
            if not url:
                continue
            media_id = str(media.get('id') or f'{post_id}_{idx:02d}')
            ext = 'mp4' if media_type == 'video' else None
            entry = {
                'id': media_id,
                'title': title,
                'uploader': username,
                'uploader_id': str(author.get('id') or '') or None,
                'webpage_url': f'https://onlyfans.com/{post_id}/{username}' if username else None,
                'timestamp': int_or_none(post.get('postedAtPrecise')),
            }
            if media_type == 'video':
                entry.update({'url': url, 'ext': ext})
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
