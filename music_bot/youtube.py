from contextlib import suppress
import traceback
from typing import Any
from unidecode import unidecode
from urllib.parse import urlparse, parse_qs
from youtubesearchpython.__future__ import Playlist, Video, VideosSearch

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
    
class YoutubePlaylist():
    def __init__(self, playlist_data: dict[str, Any]):
        self.videos: list[YoutubeVideo] = [YoutubeVideo(video_data) for video_data in playlist_data["videos"]]
        self.video_ids: list[str] = [video.video_id for video in self.videos]
        self.video_urls: list[str] = [id_to_url(id) for id in self.video_ids]
    
    @classmethod
    async def from_url(cls, url: str):
        try:
            playlist_data = await Playlist.getVideos(url)
            print(playlist_data.keys())
            for video_data in playlist_data["videos"]:
                video_formats = await Video.getFormats(video_data["id"], timeout=REQUEST_TIMEOUT)
                video_data.update(video_formats)
        except Exception as e:
            traceback.print_exception(e)
            # if not videos or "videos" not in videos or "id" not in videos["videos"]:
            #     await self.ctx.send(f"YouTube playlist \"{url}\" was not available.")
            #     raise CommandError
        return cls(playlist_data)

class YoutubeVideo():
    TARGET_MIME_TYPE = "audio/webm; codecs=\"opus\""

    def __init__(self, video_data: dict[str, Any]) -> None:
        print("creating yt object")
        self.video_id: str = video_data["id"]
        self.video_url: str = video_data["link"]
        self.title: str = video_data["title"]
        self.channel_name: str = video_data["channel"]["name"]
        self.channel_url: str = video_data["channel"]["link"]
        self.thumbnail_url: str = video_data["thumbnails"][0]["url"]

        duration = video_data["duration"]
        if isinstance(duration, str):
            time_units = video_data["duration"].split(":")
            seconds = int(time_units[-1])
            minutes = int(time_units[-2]) if len(time_units) > 1 else 0
            hours = int(time_units[-3]) if len(time_units) > 2 else 0
            self.duration: int = hours * 3600 + minutes * 60 + seconds
        else:
            self.duration: int = int(duration["secondsText"])
            minutes, seconds = divmod(self.duration, 60)
            hours, minutes = divmod(minutes, 60)
        self.formatted_duration: str = f"{str(hours).zfill(2)}:{str(minutes).zfill(2)}:{str(seconds).zfill(2)}"
        
        streaming_data = video_data["streamingData"]
        adaptive_formats = streaming_data["adaptiveFormats"]
        target_streams = [stream for stream in adaptive_formats if stream["mimeType"] == self.TARGET_MIME_TYPE]
        best_stream = max(target_streams, key = lambda stream: stream["bitrate"])
        self.stream_url: str = best_stream["url"]

    @classmethod
    async def from_search_query(cls, search_query: str):
        try:
            if not search_query:
                return None
            search = VideosSearch(unidecode(search_query), limit=1, timeout=REQUEST_TIMEOUT)
            result = await search.next()
            if not result or "result" not in result or len(result["result"]) == 0 or "id" not in result["result"][0]:
                return None
            video_data = result["result"][0]
            video_formats = await Video.getFormats(video_data["id"], timeout=REQUEST_TIMEOUT)
            video_data.update(video_formats)
        except Exception as e:
            traceback.print_exception(e)
        return cls(video_data)

    @classmethod
    async def from_url(cls, url: str):
        id = url_to_id(url)
        return await YoutubeVideo.from_id(id)

    @classmethod
    async def from_id(cls, id: str):
        video_data = await Video.get(id, timeout=REQUEST_TIMEOUT)
        if not video_data or "id" not in video_data:
            return None
        return cls(video_data)