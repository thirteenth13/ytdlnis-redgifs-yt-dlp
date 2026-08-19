#!/usr/bin/env python3
from pathlib import Path
import sys

path = Path('yt_dlp/extractor/tiktok.py')
text = path.read_text(encoding='utf-8')

# This patch owns TikTokUserIE profile/feed auth and persistent secUid reuse.
# Upstream now already uses impersonate=True for the profile page, so support
# both the older and current request shapes.

old_profile_legacy = '''        else:
            webpage = self._download_webpage(
                self._UPLOADER_URL_FORMAT % user_name, user_name,
                'Downloading user webpage', 'Unable to download user webpage',
                fatal=False, headers=self._generate_blockbuster_headers()) or ''
'''
old_profile_current = '''        else:
            webpage = self._download_webpage(
                self._UPLOADER_URL_FORMAT % user_name, user_name,
                'Downloading user webpage', 'Unable to download user webpage',
                impersonate=True, fatal=False, headers=self._generate_blockbuster_headers()) or ''
'''
new_profile = '''        else:
            cookie_names = set(self._get_cookies('https://www.tiktok.com/'))
            use_auth_impersonation = bool(cookie_names & {'sessionid', 'sessionid_ss', 'sid_tt'})
            if use_auth_impersonation:
                self.write_debug('Using Chrome impersonation for authenticated TikTok user profile request')
            webpage = self._download_webpage(
                self._UPLOADER_URL_FORMAT % user_name, user_name,
                'Downloading user webpage', 'Unable to download user webpage',
                impersonate='chrome' if use_auth_impersonation else True,
                fatal=False, headers=self._generate_blockbuster_headers()) or ''
'''

if 'Using Chrome impersonation for authenticated TikTok user profile request' not in text:
    if old_profile_current in text:
        text = text.replace(old_profile_current, new_profile, 1)
    elif old_profile_legacy in text:
        text = text.replace(old_profile_legacy, new_profile, 1)
    else:
        print('ERROR: Could not locate TikTokUserIE profile webpage block', file=sys.stderr)
        sys.exit(2)

# YTDLnis watched-source downloads use the profile URL together with -I N.
# Consult the persistent secUid cache before attempting private-profile lookup.
old_real_start = '''    def _real_extract(self, url):
        user_name, sec_uid = self._match_id(url), None
        if re.fullmatch(r'MS4wLjABAAAA[\\w-]{64}', user_name):
'''
new_real_start = '''    def _real_extract(self, url):
        user_name, sec_uid = self._match_id(url), None

        if not re.fullmatch(r'MS4wLjABAAAA[\\w-]{64}', user_name):
            cached_sec_uid = self._downloader.cache.load('tiktok-secuid', user_name)
            if isinstance(cached_sec_uid, str) and cached_sec_uid.startswith('MS4wLjABAAAA'):
                self.write_debug(f'Using cached TikTok secUid for watched profile @{user_name}')
                return self.playlist_result(
                    self._entries(cached_sec_uid, user_name, False), cached_sec_uid, user_name)

        if re.fullmatch(r'MS4wLjABAAAA[\\w-]{64}', user_name):
'''

if 'Using cached TikTok secUid for watched profile' not in text:
    if old_real_start not in text:
        print('ERROR: Could not locate TikTokUserIE._real_extract start', file=sys.stderr)
        sys.exit(3)
    text = text.replace(old_real_start, new_real_start, 1)

old_entries = '''    def _entries(self, sec_uid, user_name, fail_early=False):
        display_id = user_name or sec_uid
        seen_ids = set()
'''
new_entries = '''    def _entries(self, sec_uid, user_name, fail_early=False):
        display_id = user_name or sec_uid
        if user_name and isinstance(sec_uid, str) and sec_uid.startswith('MS4wLjABAAAA'):
            self._downloader.cache.store('tiktok-secuid', user_name, sec_uid)
            self.write_debug(f'Cached TikTok secUid for @{user_name}')
        seen_ids = set()
'''

if "Cached TikTok secUid for @{user_name}" not in text:
    if old_entries not in text:
        print('ERROR: Could not locate TikTokUserIE._entries start', file=sys.stderr)
        sys.exit(4)
    text = text.replace(old_entries, new_entries, 1)

old_feed = '''                response = self._download_json(
                    self._API_BASE_URL, display_id, f'Downloading page {page}',
                    query=self._build_web_query(sec_uid, cursor))
'''
new_feed = '''                cookie_names = set(self._get_cookies('https://www.tiktok.com/'))
                use_auth_impersonation = bool(cookie_names & {'sessionid', 'sessionid_ss', 'sid_tt'})
                if use_auth_impersonation and page == 1:
                    self.write_debug('Using Chrome impersonation for authenticated TikTok user feed requests')
                response = self._download_json(
                    self._API_BASE_URL, display_id, f'Downloading page {page}',
                    query=self._build_web_query(sec_uid, cursor),
                    impersonate='chrome' if use_auth_impersonation else None)
'''

if 'Using Chrome impersonation for authenticated TikTok user feed requests' not in text:
    if old_feed not in text:
        print('ERROR: Could not locate TikTokUserIE user-feed request block', file=sys.stderr)
        sys.exit(5)
    text = text.replace(old_feed, new_feed, 1)

path.write_text(text, encoding='utf-8')
print(f'Patched {path}: watched TikTok profiles reuse cached secUid; authenticated profile/feed requests use Chrome impersonation')
