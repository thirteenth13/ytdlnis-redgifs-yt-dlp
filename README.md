# YTDLnis RedGifs thumbnail custom yt-dlp source

This repository builds the current upstream **yt-dlp** with one small change in
`yt_dlp/extractor/redgifs.py`: RedGifs entries get a `thumbnail` field. It is
intended for YTDLnis playlist/profile previews.

## What the patch adds

The extractor tries these RedGifs API fields in order:

1. `urls.poster`
2. `urls.thumbnail`
3. `poster`
4. `thumbnail`
5. `posterUrl`
6. `thumbnailUrl`
7. `mobilePosterUrl`
8. fallback: `https://thumbs2.redgifs.com/<id>-poster.jpg`

Nothing else in the RedGifs extractor is changed.

## Create your custom source

1. Create an empty **public GitHub repository**, for example:
   `YOURNAME/ytdlnis-redgifs-yt-dlp`
2. Upload **all files from this ZIP** to the root of that repository, including
   `.github/workflows/build-release.yml`.
3. In the GitHub repository open **Actions → Build patched yt-dlp → Run workflow**.
4. Wait for the run to finish.
5. Open **Releases**. A release should contain:
   - `yt-dlp`
   - `SHA2-256SUMS`
   - `_update_spec`

The workflow also runs automatically once per day so the custom source tracks
upstream yt-dlp.

## Add it to YTDLnis

In YTDLnis:

`More → Settings → Updating → yt-dlp Source → Add`

Use:

`YOURNAME/ytdlnis-redgifs-yt-dlp@latest`

Then select that source and choose **Install new version of yt-dlp**.

YTDLnis implements custom sources by invoking yt-dlp's `--update-to
user/repo@...` mechanism.

## Verify

In YTDLnis Terminal:

    yt-dlp --verbose --skip-download --print "%(thumbnail)s" "https://www.redgifs.com/watch/cloudyignorantghostshrimp"

Expected: an image URL instead of `NA`.

Then open a RedGifs `/users/...` profile again. If YTDLnis uses the metadata
returned by yt-dlp for the playlist UI, the item previews should populate.

## Roll back

In YTDLnis choose the normal **Nightly** (or Stable) yt-dlp source and install
it again.

## Important

If upstream changes the structure of `redgifs.py`, the workflow intentionally
fails instead of silently applying a wrong patch. Update `patch_redgifs.py`
when that happens.

# TikTok patch bundle for ytdlnis-redgifs-yt-dlp

This extends the existing RedGifs-patched yt-dlp build.

## Normal TikTok videos

The build uses this Android app profile by default:

    /musical_ly/35.1.3/2023501030/1233

This is the profile that successfully returned API metadata in the Android/YTDLnis test.

Normal videos still use upstream `_parse_aweme_video_app()`.
If app API lookup fails, upstream webpage fallback remains unchanged.

## TikTok photo/slideshow posts

When the app API returns `image_post_info.images` (or compatible image-list forms),
the extractor returns a yt-dlp playlist containing the individual image URLs.

Expected output is individual files such as:

    7604865440145280263_01.jpg
    7604865440145280263_02.jpg
    7604865440145280263_03.webp

No MP4 is created and ffmpeg is not used to combine images.

## Release history fix

The included workflow does not delete old GitHub releases/tags, avoiding YTDLnis
errors when it still references an older concrete tag.

## Install

Repository:

    thirteenth13/ytdlnis-redgifs-yt-dlp

1. Upload `patch_tiktok.py` to the repository root.
2. Replace `.github/workflows/build-release.yml` with `build-release.yml`.
3. Keep the existing `patch_redgifs.py`.
4. Run Actions -> Build patched yt-dlp -> Run workflow.
5. Install/update the new custom yt-dlp build in YTDLnis.

## Test normal video

    yt-dlp --verbose "NORMAL_TIKTOK_VIDEO_URL"

Debug should contain:

    'app_name': 'musical_ly'
    'app_version': '35.1.3'
    'manifest_app_version': '2023501030'
    'aid': '1233'

## Test slideshow

    yt-dlp --verbose "TIKTOK_SLIDESHOW_URL"

Expected: a playlist of individual image entries instead of only the music MP3.

TikTok changes frequently. The patch script fails safely if upstream changes the
specific code blocks it expects.
