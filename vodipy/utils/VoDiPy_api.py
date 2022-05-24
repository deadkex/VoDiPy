import asyncio
import json

import aiohttp
try:
    import yt_dlp.utils as yt_utils
    from yt_dlp import YoutubeDL as YtDL
except ImportError:
    import youtube_dl.utils as yt_utils
    from youtube_dl import YoutubeDL as YtDL

from VoDiPy_secrets import youtube_api_key
from VoDiPy_defines import MusicPlayerSettings as MPSettings


YT_API_URL = "https://www.googleapis.com/youtube/v3/"


async def _yt_api_fetcher(link: str):
    """Get data from the youtube api

    :param link: youtube api get link
    :return: data or None
    """
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=7)) as session:
            async with session.get(f"{YT_API_URL}{link}") as response:
                data = await response.json()
    except (json.decoder.JSONDecodeError, aiohttp.ServerTimeoutError):
        return None
    if data.get("error"):
        return None
    return data


async def yt_api_playlist_songs_count(pl_id: str):
    """
    https://developers.google.com/youtube/v3/docs/playlists/list?hl=en

    :param pl_id: playlist id
    :return: count or None
    """
    # part can be: contentDetails,id,snippet,status
    link = f"playlistItems?playlistId={pl_id}&key={youtube_api_key}&part=status"
    data = await _yt_api_fetcher(link)
    return None if not data else data["pageInfo"]["totalResults"]


async def yt_api_playlist_data(pl_id: str, next_page_token: str = None):
    """
    https://developers.google.com/youtube/v3/docs/playlists/list?hl=en

    :param pl_id: playlist id
    :param next_page_token: next page token
    :return: data or None
    """
    link = f"playlistItems?playlistId={pl_id}&key={youtube_api_key}&part=status,snippet&maxResults=50"
    if next_page_token:
        link += f"&pageToken={next_page_token}"
    data = await _yt_api_fetcher(link)
    return None if (not data or data["pageInfo"]["totalResults"] == 0) else data


async def yt_api_video_data(v_id: str):
    """
    https://developers.google.com/youtube/v3/docs/videos/list?hl=en

    :param v_id: video id
    :return: data or None
    """
    link = f"videos?id={v_id}&key={youtube_api_key}&part=status,snippet"
    data = await _yt_api_fetcher(link)
    if not data or data["pageInfo"]["totalResults"] == 0 or data["items"][0]["status"]["privacyStatus"] != "public":
        return None
    return data


async def yt_dl_data(link: str, playlist_pos: int = None):
    """Used for non-youtube audio sources

    :param link: non-youtube link
    :param playlist_pos: if a video of a playlist should be loaded
    :return:
    """
    ydl_opt = {
        "format": "bestaudio/best",  # worstaudio/worst
        "noplaylist": MPSettings.no_playlist,  # if video of a playlist is sent, use video
        # "playlistend": 50,  # max 50 videos of a playlist
        "ignoreerrors": True,  # ignore errors, just continue
        "quiet": True,  # prevent logging status to console
        "no_warnings": True,
    }
    if playlist_pos is not None:
        ydl_opt["playlistitems"] = playlist_pos
    try:
        with YtDL(ydl_opt) as ytdl:
            data = await asyncio.to_thread(ytdl.extract_info, link, download=False)
    except yt_utils.YoutubeDLError:
        return None
    return data
