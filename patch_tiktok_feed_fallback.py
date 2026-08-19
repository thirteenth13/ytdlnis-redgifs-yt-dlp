#!/usr/bin/env python3
from pathlib import Path
import sys

path = Path('yt_dlp/extractor/tiktok.py')
text = path.read_text(encoding='utf-8')

helper_marker = "    def _real_extract(self, url):\n"
helper = '''    def _extract_aweme_from_user_feed(self, url, video_id):
        # Last-resort fallback for cases where both the Android app API and
        # single-post webpage fail. Resolve secUid from the authenticated
        # profile page first, then reuse TikTok's user-feed API.
        try:
            path_parts = [p for p in urllib.parse.urlparse(url).path.split('/') if p]
            user_name = next((p[1:] for p in path_parts if p.startswith('@')), None)
            if not user_name:
                return None

            user_ie = TikTokUserIE(self._downloader)
            cookie_names = set(user_ie._get_cookies('https://www.tiktok.com/'))
            use_auth_impersonation = bool(cookie_names & {'sessionid', 'sessionid_ss', 'sid_tt'})
            sec_uid = None

            # For private profiles this is more reliable than the public
            # user/detail and embed fallbacks when authenticated cookies exist.
            if use_auth_impersonation:
                self.write_debug('Resolving TikTok user-feed secUid from authenticated profile page')
                profile_page = user_ie._download_webpage(
                    user_ie._UPLOADER_URL_FORMAT % user_name, user_name,
                    note='Resolving user ID from authenticated profile page',
                    errnote='Unable to resolve user ID from authenticated profile page',
                    fatal=False, headers=user_ie._generate_blockbuster_headers(),
                    impersonate='chrome') or ''
                profile_detail = traverse_obj(
                    user_ie._get_universal_data(profile_page, user_name),
                    ('webapp.user-detail', {dict})) or {}
                sec_uid = traverse_obj(
                    profile_detail, ('userInfo', 'user', 'secUid', {str}))

            if not sec_uid and hasattr(user_ie, '_extract_sec_uid_from_web_api'):
                sec_uid = user_ie._extract_sec_uid_from_web_api(user_name)
            if not sec_uid and hasattr(user_ie, '_extract_sec_uid_from_app'):
                sec_uid = user_ie._extract_sec_uid_from_app(user_name)
            if not sec_uid:
                sec_uid = user_ie._extract_sec_uid_from_embed(user_name)
            if not sec_uid:
                return None

            cursor = int(time.time() * 1E3)
            # Keep this bounded. It is intended mainly for recent posts and
            # avoids turning a single-post request into a full profile crawl.
            for page in range(1, 6):
                response = user_ie._download_json(
                    user_ie._API_BASE_URL, user_name,
                    note=f'Looking up post in user feed (page {page})',
                    errnote='Unable to look up post in user feed',
                    fatal=False,
                    query=user_ie._build_web_query(sec_uid, cursor),
                    impersonate='chrome' if use_auth_impersonation else None) or {}

                for item in traverse_obj(response, ('itemList', ..., {dict})):
                    if str(item.get('id')) == str(video_id):
                        self.write_debug(f'Found {video_id} in TikTok user feed fallback')
                        return item

                if not response.get('hasMorePrevious') and not response.get('hasMore'):
                    break
                next_cursor = traverse_obj(
                    response, (('cursor', None), {int_or_none}, any))
                if next_cursor is None:
                    next_cursor = traverse_obj(
                        response, ('itemList', -1, 'createTime', {lambda x: int(x * 1E3)}))
                if next_cursor is None or next_cursor == cursor:
                    cursor -= 7 * 86_400_000
                else:
                    cursor = next_cursor
        except Exception as e:
            self.report_warning(f'TikTok user-feed fallback failed: {e}', video_id=video_id)
        return None

'''

# Replace our previous helper when present; otherwise insert it.
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
print('TikTok: single-post fallback resolves private-user secUid from authenticated profile and uses Chrome user-feed requests')
