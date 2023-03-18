import traceback
from contextlib import suppress
from discord.ext.commands import Context
from typing import Any
from urllib.parse import parse_qs, urlparse

from unidecode import unidecode
from youtubesearchpython.__future__ import Playlist, Video, VideosSearch

from .time_utils import format_time_str, time_str_to_seconds

REQUEST_TIMEOUT = 60 # seconds

# Returns youtube video url given its id
def id_to_url(id):
    return "https://www.youtube.com/watch?v=" + id

# Returns a youtube video id given its url
# Will return None if there is no valid id
# If ignore_playlist is False, will return None if no playlist id is found, even if there is a valid video id
def url_to_id(url, ignore_playlist = True):
    # Examples:
    # - http://youtu.be/SA2iWivDJiE
    # - http://www.youtube.com/watch?v=_oPAwA_Udwc&feature=feedu
    # - http://www.youtube.com/embed/SA2iWivDJiE
    # - http://www.youtube.com/v/SA2iWivDJiE?version=3&amp;hl=en_US
    try:
        query = urlparse(url)
        if query.hostname == 'youtu.be' and ignore_playlist: return query.path[1:]
        if query.hostname in {'www.youtube.com', 'youtube.com', 'music.youtube.com', 'm.youtube.com'}:
            if not ignore_playlist:
            # use case: get playlist id not current video in playlist
                with suppress(KeyError):
                    return parse_qs(query.query)['list'][0]
                return None
            if query.path == '/watch': return parse_qs(query.query)['v'][0]
            if query.path[:7] == '/watch/': return query.path.split('/')[1]
            if query.path[:7] == '/embed/': return query.path.split('/')[2]
            if query.path[:3] == '/v/': return query.path.split('/')[2]
    except Exception as e:
        print("url to id")
        traceback.print_exception(e)
    # returns None for invalid YouTube url

def is_yt_video(url):
    return url_to_id(url, ignore_playlist = True) is not None

def is_yt_playlist(url):
    return url_to_id(url, ignore_playlist = False) is not None

def parse_duration(duration: int):
    minutes, seconds = divmod(duration, 60)
    hours, minutes = divmod(minutes, 60)
    return hours, minutes, seconds

async def get_id_from_youtube_search(search_query: str) -> str:
    if not search_query:
        return None
    search = VideosSearch(unidecode(search_query), limit=1, timeout=REQUEST_TIMEOUT)
    result = await search.next()
    if not result or "result" not in result or len(result["result"]) == 0 or "id" not in result["result"][0]:
        return None
    return result["result"][0]["id"]

class YoutubePlaylist():
    def __init__(self, playlist_data: dict[str, Any]):
        self.videos: list[YoutubeVideo] = [YoutubeVideo(video_data) for video_data in playlist_data["videos"]]
        self.video_ids: list[str] = [video.video_id for video in self.videos]
        self.video_urls: list[str] = [id_to_url(id) for id in self.video_ids]
    
    # @classmethod
    # async def from_url(cls, url: str):
    #     try:
    #         playlist_data = await Playlist.getVideos(url)
    #         print(playlist_data.keys())
    #         for video_data in playlist_data["videos"]:
    #             video_formats = await Video.getFormats(video_data["id"], timeout=REQUEST_TIMEOUT)
    #             video_data.update(video_formats)
    #     except Exception as e:
    #         traceback.print_exception(e)
    #     return cls(playlist_data)

class YoutubeVideo():
    TARGET_MIME_TYPE = "audio/webm; codecs=\"opus\""

    def __init__(self, video_data: dict[str, Any]) -> None:
        print("creating yt object")
        self.video_id: str = video_data["id"]
        self.video_url: str = video_data["link"]
        self.title: str = video_data["title"]
        self.video_link_markdown: str = f"[{self.title}]({self.video_url})"

        self.channel_name: str = video_data["channel"]["name"]
        self.channel_url: str = video_data["channel"]["link"]
        self.channel_link_markdown: str = f"[{self.channel_name}]({self.channel_url})"

        self.thumbnail_url: str = video_data["thumbnails"][0]["url"]

        duration = video_data["duration"]
        self.duration: int = time_str_to_seconds(duration) if isinstance(duration, str) else int(duration["secondsText"])
        self.formatted_duration: str = format_time_str(self.duration)
        
        streaming_data = video_data["streamingData"]
        adaptive_formats = streaming_data["adaptiveFormats"]
        target_streams = [stream for stream in adaptive_formats if stream["mimeType"] == self.TARGET_MIME_TYPE]
        if not target_streams:
            print(streaming_data)
            print(adaptive_formats)
            target_streams = [stream for stream in adaptive_formats if "audio" in stream["mimeType"] and "video" not in stream["mimeType"]]
            print(target_streams)
        best_stream = max(target_streams, key = lambda stream: stream["bitrate"])
        self.stream_url: str = best_stream["url"]

    # @classmethod
    # async def from_search_query(cls, search_query: str):
    #     try:
    #         if not search_query:
    #             return None
    #         search = VideosSearch(unidecode(search_query), limit=1, timeout=REQUEST_TIMEOUT)
    #         result = await search.next()
    #         if not result or "result" not in result or len(result["result"]) == 0 or "id" not in result["result"][0]:
    #             return None
    #         video_data = result["result"][0]
    #         video_formats = await Video.getFormats(video_data["id"], timeout=REQUEST_TIMEOUT)
    #         video_data.update(video_formats)
    #     except Exception as e:
    #         traceback.print_exception(e)
    #     return cls(video_data)

    # @classmethod
    # async def from_url(cls, url: str):
    #     id = url_to_id(url)
    #     return await YoutubeVideo.from_id(id)

    # @classmethod
    # async def from_id(cls, id: str):
    #     video_data = await Video.get(id, timeout=REQUEST_TIMEOUT)
    #     if not video_data or "id" not in video_data:
    #         return None
    #     return cls(video_data)

# TODO: Sometimes, youtube results from search queries randomly don't have streaming data, I may have to add retry logic to get it
# Sometimes, youtube results from search queries have streaming data, but not the desired mime type. Add logic to get the best available stream.
class YoutubeFactory:
    def __init__(self) -> None:
        self.ctx: Context = None
    
    async def create_yt_videos_from_yt_playlist_url(self, yt_playlist_url: str):
        yt_playlist_data = await Playlist.getVideos(yt_playlist_url)
        if not yt_playlist_data:
            await self.ctx.send(f"Youtube playlist url \"{yt_playlist_url}\" did not yield any results.")
            return
        if "videos" not in yt_playlist_data or not yt_playlist_data["videos"]:
            await self.ctx.send(f"Youtube playlist at \"{yt_playlist_url}\" did not have any videos.")
            return
        found_streamable_video = False
        for yt_video_data in yt_playlist_data["videos"]:
            if not (await self.update_yt_video_streaming_data(yt_video_data)):
                await self.ctx.send(f"**{yt_video_data['title']}** is not streamable. Skipping...")
            else:
                found_streamable_video = True
                yield YoutubeVideo(yt_video_data)
        if not found_streamable_video:
            await self.ctx.send(f"Youtube playlist at \"{yt_playlist_url}\" did not have any streamable videos.")

    async def create_yt_video_from_search_query(self, yt_search_query: str):
        if not yt_search_query:
            await self.ctx.send("Invalid youtube search query.")
            return None
        search = VideosSearch(unidecode(yt_search_query), limit=1, timeout=REQUEST_TIMEOUT)
        result = await search.next()
        if not result or not result["result"]:
            await self.ctx.send(f"Youtube search \"{yt_search_query}\" did not yield any results.")
            return None
        yt_video_data = result["result"][0]
        if not (await self.update_yt_video_streaming_data(yt_video_data)):
            await self.ctx.send(f"**{yt_video_data['title']}** is not streamable.")
            return None
        return YoutubeVideo(yt_video_data)
    
    async def create_yt_video_from_url(self, yt_video_url: str):
        yt_video_id = url_to_id(yt_video_url)
        yt_video = await self.create_yt_video_from_id(yt_video_id)
        if not yt_video:
            await self.ctx.send(f"Youtube url \"{yt_video_url}\" did not yield any results.")
        return yt_video
    
    async def create_yt_video_from_id(self, yt_video_id: str):
        yt_video_data = await Video.get(yt_video_id, timeout=REQUEST_TIMEOUT)
        if not yt_video_data:
            await self.ctx.send(f"Youtube id \"{yt_video_id}\" did not yield any results.")
            return None
        if not (await self.update_yt_video_streaming_data(yt_video_data)):
            await self.ctx.send(f"**{yt_video_data['title']}** is not streamable.")
            return None
        return YoutubeVideo(yt_video_data)

    async def update_yt_video_streaming_data(self, yt_video_data: dict[str, Any], tries=3) -> bool:
        while tries > 0 and ("streamingData" not in yt_video_data or not yt_video_data["streamingData"]):
            if tries < 3:
                print("Had to try again")
            streaming_data = await Video.getFormats(yt_video_data["id"], timeout=REQUEST_TIMEOUT)
            yt_video_data.update(streaming_data)
            tries -= 1
        if tries == 0:
            print("video data", yt_video_data)
            print("streaming data: ", streaming_data)
        return tries > 0