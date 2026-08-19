#!/usr/bin/env python3
from pathlib import Path
import sys

path = Path('yt_dlp/extractor/tiktok.py')
text = path.read_text(encoding='utf-8')

helper_marker = "    def _real_extract(self, url):\n"
helper = '''    def _extract_aweme_from_user_feed(self, url, video_id):
        # Last-resort fallback for authenticated/private TikTok posts.
        # Reuse a persistently cached secUid whenever possible, then fall back
        # to resolving it from authenticated profile data and walk the feed.
        try:
            path_parts = [p for p in urllib.parse.urlparse(url).path.split('/') if p]
            user_name = next((p[1:] for p in path_parts if p.startswith('@')), None)
            if not user_name:
                return None

            user_ie = TikTokUserIE(self._downloader)
            cookie_names = set(user_ie._get_cookies('https://www.tiktok.com/'))
            use_auth_impersonation = bool(cookie_names & {'sessionid', 'sessionid_ss', 'sid_tt'})

            sec_uid = self._downloader.cache.load('tiktok-secuid', user_name)
            if isinstance(sec_uid, str) and sec_uid.startswith('MS4wLjABAAAA'):
                self.write_debug(f'Using cached TikTok secUid for @{user_name}')
            else:
                sec_uid = None

            if not sec_uid and use_auth_impersonation:
                self.write_debug('Resolving TikTok user-feed secUid from authenticated profile page')
                profile_page = user_ie._download_webpage(
                    user_ie._UPLOADER_URL_FORMAT % user_name, user_name,
                    note='Resolving user ID from authenticated profile page',
                    errnote='Unable to resolve user ID from authenticated profile page',
                    fatal=False, headers=user_ie._generate_blockbuster_headers(),
                    impersonate='chrome') or ''

                try:
                    universal = user_ie._get_universal_data(profile_page, user_name) or {}
                except Exception:
                    universal = {}
                profile_detail = traverse_obj(universal, ('webapp.user-detail', {dict})) or {}
                sec_uid = traverse_obj(profile_detail, ('userInfo', 'user', 'secUid', {str}))

                if not sec_uid:
                    sec_uid = self._search_regex(
                        (r'"secUid"\\s*:\\s*"(MS4wLjABAAAA[^"\\\\]+)"',
                         r'"sec_uid"\\s*:\\s*"(MS4wLjABAAAA[^"\\\\]+)"',
                         r'\\bsecUid(?:%22|%3A|=)+(MS4wLjABAAAA[A-Za-z0-9_-]+)'),
                        profile_page, 'authenticated profile secUid',
                        default=None, fatal=False)
                if sec_uid:
                    self.write_debug('Resolved TikTok secUid from authenticated profile page')

            if not sec_uid and hasattr(user_ie, '_extract_sec_uid_from_web_api'):
                sec_uid = user_ie._extract_sec_uid_from_web_api(user_name)
            if not sec_uid and hasattr(user_ie, '_extract_sec_uid_from_app'):
                sec_uid = user_ie._extract_sec_uid_from_app(user_name)
            if not sec_uid:
                sec_uid = user_ie._extract_sec_uid_from_embed(user_name)
            if not sec_uid:
                self.report_warning('Unable to resolve TikTok secUid for user-feed fallback', video_id=video_id)
                return None

            if isinstance(sec_uid, str) and sec_uid.startswith('MS4wLjABAAAA'):
                self._downloader.cache.store('tiktok-secuid', user_name, sec_uid)
                self.write_debug(f'Cached TikTok secUid for @{user_name}')

            cursor = int(time.time() * 1E3)
            seen_cursors = set()
            for page in range(1, 251):
                if cursor in seen_cursors:
                    break
                seen_cursors.add(cursor)
                response = user_ie._download_json(
                    user_ie._API_BASE_URL, user_name,
                    note=f'Looking up post in user feed (page {page})',
                    errnote='Unable to look up post in user feed',
                    fatal=False,
                    query=user_ie._build_web_query(sec_uid, cursor),
                    impersonate='chrome' if use_auth_impersonation else None) or {}

                items = list(traverse_obj(response, ('itemList', ..., {dict})))
                for item in items:
                    if str(item.get('id')) == str(video_id):
                        self.write_debug(f'Found {video_id} in TikTok user feed fallback on page {page}')
                        return item

                if not items:
                    break
                if not response.get('hasMorePrevious') and not response.get('hasMore'):
                    break

                next_cursor = traverse_obj(response, ('cursor', {int_or_none}))
                if next_cursor is None:
                    oldest_time = min(filter(None, (
                        traverse_obj(item, ('createTime', {int_or_none})) for item in items)),
                        default=None)
                    if oldest_time:
                        next_cursor = oldest_time * 1000 - 1
                if next_cursor is None or next_cursor == cursor:
                    cursor -= 7 * 86_400_000
                else:
                    cursor = next_cursor
        except Exception as e:
            self.report_warning(f'TikTok user-feed fallback failed: {e}', video_id=video_id)
        return None

'''

start = text.find('    def _extract_aweme_from_user_feed(self, url, video_id):\n')
if start != -1:
    end = text.find('    def _real_extract(self, url):\n', start)
    if end == -1:
        print('ERROR: Could not locate end of TikTok user-feed fallback helper', file=sys.stderr)
        sys.exit(2)
    text = text[:start] + helper + text[end:]
elif helper_marker in text:
    text = text.replace(helper_marker, helper + helper_marker, 1)
else:
    print('ERROR: Could not locate TikTokIE._real_extract marker', file=sys.stderr)
    sys.exit(2)

old_call = "        video_data, status = self._extract_web_data_and_status(url, video_id)\n"
new_call = '''        try:
            video_data, status = self._extract_web_data_and_status(url, video_id)
        except ExtractorError as e:
            self.report_warning(
                f'{e.orig_msg}; trying TikTok user-feed fallback', video_id=video_id)
            video_data = self._extract_aweme_from_user_feed(url, video_id)
            status = 0 if video_data else -1
            if not video_data:
                raise
'''

if 'trying TikTok user-feed fallback' not in text:
    if old_call not in text:
        print('ERROR: Could not locate TikTok web extraction call', file=sys.stderr)
        sys.exit(3)
    text = text.replace(old_call, new_call, 1)

path.write_text(text, encoding='utf-8')
print(f'Patched {path}')
print('TikTok: private-profile secUid is persistently cached; user-feed fallback searches up to 250 pages')
