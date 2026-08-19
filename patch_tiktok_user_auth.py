#!/usr/bin/env python3
from pathlib import Path
import sys

path = Path('yt_dlp/extractor/tiktok.py')
text = path.read_text(encoding='utf-8')

# 1) Authenticated profile page: use Chrome impersonation when login cookies exist.
old_profile = '''        else:
            webpage = self._download_webpage(
                self._UPLOADER_URL_FORMAT % user_name, user_name,
                'Downloading user webpage', 'Unable to download user webpage',
                fatal=False, headers=self._generate_blockbuster_headers()) or ''
'''
new_profile = '''        else:
            cookie_names = set(self._get_cookies('https://www.tiktok.com/'))
            use_auth_impersonation = bool(cookie_names & {'sessionid', 'sessionid_ss', 'sid_tt'})
            if use_auth_impersonation:
                self.write_debug('Using Chrome impersonation for authenticated TikTok user profile request')
            webpage = self._download_webpage(
                self._UPLOADER_URL_FORMAT % user_name, user_name,
                'Downloading user webpage', 'Unable to download user webpage',
                fatal=False, headers=self._generate_blockbuster_headers(),
                impersonate='chrome' if use_auth_impersonation else None) or ''
'''

if 'Using Chrome impersonation for authenticated TikTok user profile request' not in text:
    if old_profile not in text:
        print('ERROR: Could not locate TikTokUserIE profile webpage block', file=sys.stderr)
        sys.exit(2)
    text = text.replace(old_profile, new_profile, 1)

# 2) User feed pages used by -I playlist selection should use the same authenticated browser fingerprint.
old_entries = '''                response = self._download_json(
                    self._API_BASE_URL, display_id, f'Downloading page {page}',
                    query=self._build_web_query(sec_uid, cursor))
'''
new_entries = '''                cookie_names = set(self._get_cookies('https://www.tiktok.com/'))
                use_auth_impersonation = bool(cookie_names & {'sessionid', 'sessionid_ss', 'sid_tt'})
                if use_auth_impersonation and page == 1:
                    self.write_debug('Using Chrome impersonation for authenticated TikTok user feed requests')
                response = self._download_json(
                    self._API_BASE_URL, display_id, f'Downloading page {page}',
                    query=self._build_web_query(sec_uid, cursor),
                    impersonate='chrome' if use_auth_impersonation else None)
'''

if 'Using Chrome impersonation for authenticated TikTok user feed requests' not in text:
    if old_entries not in text:
        print('ERROR: Could not locate TikTokUserIE user-feed request block', file=sys.stderr)
        sys.exit(3)
    text = text.replace(old_entries, new_entries, 1)

# 3) Our username -> secUid web API fallback should also impersonate Chrome with login cookies.
old_webapi = '''        user_data = self._download_json(
            'https://www.tiktok.com/api/user/detail/', user_name,
            note='Resolving secondary user ID with TikTok web API',
            errnote='Unable to resolve secondary user ID with TikTok web API',
            fatal=False,
            headers=self._generate_blockbuster_headers(),
            query={
'''
new_webapi = '''        cookie_names = set(self._get_cookies('https://www.tiktok.com/'))
        use_auth_impersonation = bool(cookie_names & {'sessionid', 'sessionid_ss', 'sid_tt'})
        user_data = self._download_json(
            'https://www.tiktok.com/api/user/detail/', user_name,
            note='Resolving secondary user ID with TikTok web API',
            errnote='Unable to resolve secondary user ID with TikTok web API',
            fatal=False,
            headers=self._generate_blockbuster_headers(),
            impersonate='chrome' if use_auth_impersonation else None,
            query={
'''

if "impersonate='chrome' if use_auth_impersonation else None,\n            query={" not in text:
    if old_webapi not in text:
        print('ERROR: Could not locate custom TikTok user-detail web API block', file=sys.stderr)
        sys.exit(4)
    text = text.replace(old_webapi, new_webapi, 1)

path.write_text(text, encoding='utf-8')
print(f'Patched {path}: authenticated TikTok user profile/feed requests use Chrome impersonation')
