#!/usr/bin/env python3
from pathlib import Path
import sys

path = Path('yt_dlp/extractor/tiktok.py')
text = path.read_text(encoding='utf-8')

# This patch runs AFTER patch_tiktok_retry.py and patch_tiktok_feed_fallback.py.
# Therefore match the already-transformed app retry block, not pristine upstream.
old_start = '''    def _real_extract(self, url):
        video_id, user_id = self._match_valid_url(url).group('id', 'user_id')

        if self._KNOWN_APP_INFO:
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
new_start = '''    def _real_extract(self, url):
        video_id, user_id = self._match_valid_url(url).group('id', 'user_id')

        # If YTDLnis/yt-dlp was given a logged-in TikTok cookie jar, prefer
        # authenticated web requests. This matters for private accounts/posts:
        # the Android app API path does not reliably inherit the web session.
        cookie_names = set(self._get_cookies('https://www.tiktok.com/'))
        auth_cookie_names = tuple(name for name in (
            'sessionid', 'sessionid_ss', 'sid_tt', 'sid_guard', 'uid_tt', 'uid_tt_ss', 'ttwid'
        ) if name in cookie_names)
        has_auth_cookies = bool(set(auth_cookie_names) & {'sessionid', 'sessionid_ss', 'sid_tt'})
        if has_auth_cookies:
            self.write_debug(
                'TikTok authenticated web cookies detected: '
                + ', '.join(auth_cookie_names))
            self.write_debug('Preferring authenticated TikTok web path before app API')

        if self._KNOWN_APP_INFO and not has_auth_cookies:
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

if 'Preferring authenticated TikTok web path before app API' not in text:
    if old_start not in text:
        print('ERROR: Could not locate TikTokIE retry-transformed app-first block', file=sys.stderr)
        sys.exit(2)
    text = text.replace(old_start, new_start, 1)

# patch_tiktok_feed_fallback.py has already wrapped the web extraction call.
old_web = '''        try:
            video_data, status = self._extract_web_data_and_status(url, video_id)
        except ExtractorError as e:
            self.report_warning(
                f'{e.orig_msg}; trying TikTok user-feed fallback', video_id=video_id)
            video_data = self._extract_aweme_from_user_feed(url, video_id)
            status = 0 if video_data else -1
            if not video_data:
                raise
'''
new_web = '''        try:
            video_data, status = self._extract_web_data_and_status(url, video_id)
        except ExtractorError as web_error:
            # For an authenticated/private request, web is preferred, but the
            # app API can still rescue a post if TikTok's webpage WAF is flaky.
            if has_auth_cookies and self._KNOWN_APP_INFO:
                try:
                    self.report_warning(
                        f'{web_error.orig_msg}; authenticated web path failed, trying TikTok app API',
                        video_id=video_id)
                    return self._extract_aweme_app(video_id)
                except ExtractorError as app_error:
                    app_error.expected = True
                    self.report_warning(
                        f'{app_error}; trying TikTok user-feed fallback', video_id=video_id)
            else:
                self.report_warning(
                    f'{web_error.orig_msg}; trying TikTok user-feed fallback', video_id=video_id)

            video_data = self._extract_aweme_from_user_feed(url, video_id)
            status = 0 if video_data else -1
            if not video_data:
                raise web_error
'''

if 'authenticated web path failed, trying TikTok app API' not in text:
    if old_web not in text:
        print('ERROR: Could not locate TikTok user-feed fallback wrapper', file=sys.stderr)
        sys.exit(3)
    text = text.replace(old_web, new_web, 1)

path.write_text(text, encoding='utf-8')
print(f'Patched {path}')
print('TikTok: logged-in cookies now prefer authenticated web path; app API and user-feed remain fallbacks')
