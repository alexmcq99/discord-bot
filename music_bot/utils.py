import re

from contextlib import suppress
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse

# Time

TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

def time_str_to_seconds(time_str: str):
    hours, minutes, seconds = parse_time_str(time_str)
    return hours * 3600 + minutes * 60 + seconds
    
def parse_time_str(time_str: str):
    time_units = time_str.split(":")
    seconds = int(time_units[-1])
    minutes = int(time_units[-2]) if len(time_units) > 1 else 0
    hours = int(time_units[-3]) if len(time_units) > 2 else 0
    return hours, minutes, seconds

def format_time_str(seconds: int, minutes: int = 0, hours: int = 0) -> str:
    if isinstance(seconds, float):
        seconds = round(seconds)
    extra_minutes, seconds = divmod(seconds, 60)
    minutes += extra_minutes
    extra_hours, minutes = divmod(minutes, 60)
    hours += extra_hours
    return f"{str(hours).zfill(2)}:{str(minutes).zfill(2)}:{str(seconds).zfill(2)}"

def format_datetime(timestamp: datetime) -> str:
    return timestamp.strftime(TIME_FORMAT)

def format_timedelta(delta: timedelta) -> int:
    return round(delta.total_seconds())

# URL parsing

def is_spotify_url(url):
    # https://open.spotify.com/track/405HNEYKGDifuMcAZvqrqA?si=f38076221d0246b5
    # https://open.spotify.com/album/643kxxjS5xPkzD4bR9vUn2?si=cuCeyEgYQm-pXKK7679ptQ
    # https://open.spotify.com/playlist/6FkEOJ76LyyajBjOoGvGXT?si=6ba13d149a1b4d1c
    pattern = re.compile(r"^https:\/\/open.spotify.com\/(?:track|album|playlist)\/[a-zA-Z0-9]+")
    return pattern.match(url)

# Returns youtube video url given its id
def yt_video_id_to_url(id):
    return "https://www.youtube.com/watch?v=" + id

# Returns a youtube video id given its url
# Will return None if there is no valid id
# If ignore_playlist is False, will return None if no playlist id is found, even if there is a valid video id
def yt_video_url_to_id(url, ignore_playlist = True):
    # Examples:
    # - http://youtu.be/SA2iWivDJiE
    # - http://www.youtube.com/watch?v=_oPAwA_Udwc&feature=feedu
    # - http://www.youtube.com/embed/SA2iWivDJiE
    # - http://www.youtube.com/v/SA2iWivDJiE?version=3&amp;hl=en_US
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
    # returns None for invalid YouTube url

def is_yt_video(url):
    return bool(yt_video_url_to_id(url, ignore_playlist = True))

def is_yt_playlist(url):
    return bool(yt_video_url_to_id(url, ignore_playlist = False))