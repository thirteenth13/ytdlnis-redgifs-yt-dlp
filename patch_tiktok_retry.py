#!/usr/bin/env python3
from pathlib import Path
import sys

path = Path('yt_dlp/extractor/tiktok.py')
text = path.read_text(encoding='utf-8')

# Retry the app API once with a fresh generated device id/session when TikTok
# returns an empty/non-JSON response. Explicit user-supplied device_id is kept.
old_app = '''        if self._KNOWN_APP_INFO:
            try:
                return self._extract_aweme_app(video_id)
            except ExtractorError as e:
                e.expected = True
                self.report_warning(f'{e}; trying with webpage')
'''
new_app = '''        if self._KNOWN_APP_INFO:
            for app_attempt in range(2):
                try:
                    return self._extract_aweme_app(video_id)
                except ExtractorError as e:
                    if app_attempt == 0 and not self._KNOWN_DEVICE_ID:
                        self.report_warning(f'{e}; retrying TikTok app API with a fresh device session')
                        self.__dict__.pop('_DEVICE_ID', None)
                        self._APP_INFO_POOL = None
                        self._APP_INFO = None
                        self._APP_USER_AGENT = None
                        time.sleep(random.uniform(1.0, 2.0))
                        continue
                    e.expected = True
                    self.report_warning(f'{e}; trying with webpage')
                    break
'''

if 'retrying TikTok app API with a fresh device session' not in text:
    if old_app not in text:
        print('ERROR: Could not locate TikTokIE app API fallback block', file=sys.stderr)
        sys.exit(2)
    text = text.replace(old_app, new_app, 1)

# Authenticated TikTok web requests are frequently rejected by the normal
# Python HTTP fingerprint even when the cookies are valid. YTDLnis ships
# curl_cffi, so automatically request Chrome impersonation whenever a login
# cookie is present. This mirrors the manually verified --impersonate chrome.
old_get = '''        def get_webpage(note='Downloading webpage'):
            res = self._download_webpage_handle(url, video_id, note, fatal=fatal, headers=headers)
            if res is False:
                return False
'''
new_get = '''        def get_webpage(note='Downloading webpage'):
            cookie_names = set(self._get_cookies('https://www.tiktok.com/'))
            use_auth_impersonation = bool(cookie_names & {'sessionid', 'sessionid_ss', 'sid_tt'})
            if use_auth_impersonation:
                self.write_debug('Using Chrome impersonation for authenticated TikTok webpage request')

            res = None
            for web_attempt in range(2):
                try:
                    res = self._download_webpage_handle(
                        url, video_id, note, fatal=fatal, headers=headers,
                        impersonate='chrome' if use_auth_impersonation else None)
                    break
                except ExtractorError as e:
                    status = getattr(e.cause, 'status', None)
                    if status != 403 or web_attempt:
                        raise
                    self.report_warning('TikTok returned HTTP 403; retrying webpage once after a short delay', video_id=video_id)
                    time.sleep(random.uniform(2.0, 4.0))
                    headers.update(self._generate_blockbuster_headers())
            if res is False:
                return False
'''

# Support updating both pristine upstream and our previous retry-patched shape.
old_retry_get = '''        def get_webpage(note='Downloading webpage'):
            res = None
            for web_attempt in range(2):
                try:
                    res = self._download_webpage_handle(url, video_id, note, fatal=fatal, headers=headers)
                    break
                except ExtractorError as e:
                    status = getattr(e.cause, 'status', None)
                    if status != 403 or web_attempt:
                        raise
                    self.report_warning('TikTok returned HTTP 403; retrying webpage once after a short delay', video_id=video_id)
                    time.sleep(random.uniform(2.0, 4.0))
                    headers.update(self._generate_blockbuster_headers())
            if res is False:
                return False
'''

if 'Using Chrome impersonation for authenticated TikTok webpage request' not in text:
    if old_get in text:
        text = text.replace(old_get, new_get, 1)
    elif old_retry_get in text:
        text = text.replace(old_retry_get, new_get, 1)
    else:
        print('ERROR: Could not locate TikTok webpage helper', file=sys.stderr)
        sys.exit(3)

path.write_text(text, encoding='utf-8')
print(f'Patched {path}: TikTok app retry + authenticated Chrome impersonation + 403 retry enabled')
