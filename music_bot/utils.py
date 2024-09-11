"""Contains utility functions used throughout the rest of the source code."""

import re
from contextlib import suppress
from datetime import datetime, timedelta
from re import Match
from urllib.parse import parse_qs, urlparse

from dateutil import tz

# Markdown


def get_link_markdown(name: str, url: str):
    """Returns a markdown hyperlink composed of the given name and url.

    Args:
        name: The name of the resource that the hyperlink will display.
        url: The url of the resource to link to.

    Returns:
        A markdown hyperlink to the given url, with the name as the displayed text.
    """
    return f"[{name}]({url})"


# Time

TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def time_str_to_seconds(time_str: str) -> int:
    """Converts a duration in the format of "HH:MM:SS" to seconds.

    Args:
        time_str: The duration, as a string.

    Returns:
        The duration as an integer, in seconds.
    """
    hours, minutes, seconds = parse_time_str(time_str)
    return hours * 3600 + minutes * 60 + seconds


def parse_time_str(time_str: str) -> tuple[int]:
    """Parses the hours, minutes, and seconds from a duration in the format of "HH:MM:SS".

    Args:
        time_str: The duration, as a string.

    Returns:
        A tuple of integers representing the hours, minutes, and seconds of the duration.
    """
    time_units = time_str.split(":")
    seconds = int(time_units[-1])
    minutes = int(time_units[-2]) if len(time_units) > 1 else 0
    hours = int(time_units[-3]) if len(time_units) > 2 else 0
    return hours, minutes, seconds


def format_time_str(seconds: int, minutes: int = 0, hours: int = 0) -> str:
    """Converts the given hours, minutes, and seconds to a time string formatted like "HH:MM:SS".

    Seconds, minutes and hours can all be over 60. The resulting duration string will account for this.

    Args:
        seconds: The seconds of the duration, as an integer. Required.
        minutes: The minutes of the duration, as an integer. Optional, defaults to 0.
        hours: The seconds of the duration, as an integer. Optional, defaults to 0.

    Returns:
        The total duration as a formatted time string, in the format "HH:MM:SS".
    """
    if isinstance(seconds, float):
        seconds = round(seconds)
    extra_minutes, seconds = divmod(seconds, 60)
    minutes += extra_minutes
    extra_hours, minutes = divmod(minutes, 60)
    hours += extra_hours
    return f"{str(hours).zfill(2)}:{str(minutes).zfill(2)}:{str(seconds).zfill(2)}"


def format_datetime(timestamp: datetime) -> str:
    """Formats a datetime object as denoted in the constant TIME_FORMAT.

    Args:
        timestamp: The datetime object to format.

    Returns:
        The datetime object formatted as a string, in the format denoted by the TIME_FORMAT constant.
    """
    return timestamp.strftime(TIME_FORMAT)


def format_timedelta(delta: timedelta) -> int:
    """Converts a timedelta object to seconds, rounded to the nearest second.

    Args:
        delta: The timedelta object to convert.

    Returns:
        The timedelta object converted to seconds, rounded to the nearest second, as an integer.
    """
    return round(delta.total_seconds())


def utc_to_pacific(timestamp: datetime) -> datetime:
    """Converts a datetime object from UTC timezone to US/Pacific timezone.

    Args:
        timestamp: The datetime object to convert.

    Returns:
        The datetime object converted to US/Pacific timezone.
    """
    return timestamp.astimezone(tz.gettz("US/Pacific"))


# URL parsing


def is_spotify_album_or_playlist(url: str) -> bool:
    """Checks if a url is a link to a Spotify album or playlist.

    Args:
        url: The url to check.

    Returns:
        True if the url links to a Spotify album or playlist, False otherwise.
    """
    result = parse_spotify_url_or_uri(url)
    if result:
        music_type = result[0]
        return music_type == "album" or music_type == "playlist"
    return False


def is_spotify_track(url: str) -> bool:
    """Checks if a url is a link to a Spotify track.

    Args:
        url: The url to check.

    Returns:
        True if the url links to a Spotify track; otherwise, False.
    """
    result = parse_spotify_url_or_uri(url)
    if result:
        music_type = result[0]
        return music_type == "track"
    return False


def parse_spotify_url_or_uri(to_parse: str) -> tuple[str]:
    if match := regex_match_spotify_url(to_parse):
        return match.groups()
    elif match := regex_match_spotify_uri(to_parse):
        return match.groups()


def regex_match_spotify_uri(uri: str) -> Match[str]:
    """Attempts to regex match a uri to a pattern for Spotify urls.

    Args:
        uri: The uri to get a regex match from.

    Returns:
        The regex match if there is one; otherwise, None. If found, the regex match will have "music_type" and
        "id" groups representing the music_type (track, album, or playlist) and the Spotify id, respectively.

    Examples:
    - spotify:album:5yTx83u3qerZF7GRJu7eFk
    """
    pattern = re.compile(
        r"^spotify:(?P<music_type>track|album|playlist):(?P<id>[a-zA-Z0-9]+)"
    )
    return pattern.match(uri)


def regex_match_spotify_url(url: str) -> Match[str]:
    """Attempts to regex match a url to a pattern for Spotify urls.

    Args:
        url: The url to get a regex match from.

    Returns:
        The regex match if there is one; otherwise, None. If found, the regex match will have "music_type" and
        "id" groups representing the music_type (track, album, or playlist) and the Spotify id, respectively.

    Examples:
    - https://open.spotify.com/track/405HNEYKGDifuMcAZvqrqA?si=f38076221d0246b5
    - https://open.spotify.com/album/643kxxjS5xPkzD4bR9vUn2?si=cuCeyEgYQm-pXKK7679ptQ
    - https://open.spotify.com/playlist/6FkEOJ76LyyajBjOoGvGXT?si=6ba13d149a1b4d1c
    """

    pattern = re.compile(
        r"^https:\/\/open.spotify.com\/(?P<music_type>track|album|playlist)\/(?P<id>[a-zA-Z0-9]+)"
    )
    return pattern.match(url)


def is_yt_video(url: str):
    """Checks if a url is a YouTube video url.

    Args:
        url: The url to check.

    Returns:
        True if the url links to a YouTube video; otherwise, False.
    """
    return bool(yt_url_to_id(url, ignore_playlist=True))


def is_yt_playlist(url: str):
    """Checks if a url is a YouTube playlist url.

    Args:
        url: The url to check.

    Returns:
        True if the url links to a YouTube playlist; otherwise, False.
    """
    return bool(yt_url_to_id(url, ignore_playlist=False))


def yt_video_id_to_url(yt_video_id: str) -> str:
    """Converts a YouTube video id to a url.

    Args:
        yt_video_id: The YouTube video id.

    Returns:
        The YouTube video url for the id.
    """
    return "https://www.youtube.com/watch?v=" + yt_video_id


def yt_url_to_id(yt_url: str, ignore_playlist: bool = True) -> str | None:
    """Converts a YouTube video url to a YouTube video or playlist id.

    Parses a YouTube url to look for video or playlist ids, depending on is_playlist.
    Note that if ignore_playlist is False, this function will return None if no playlist id is found,
    even if there is a valid video id.

    Args:
        yt_video_url: The YouTube video url.
        ignore_playlist: Whether or not to prioritize looking for a video id over a playlist id.

    Returns:
        The YouTube video or playlist id for the url if found; otherwise, None.

    Examples:
    - http://youtu.be/SA2iWivDJiE
    - http://www.youtube.com/watch?v=_oPAwA_Udwc&feature=feedu
    - http://www.youtube.com/embed/SA2iWivDJiE
    - http://www.youtube.com/v/SA2iWivDJiE?version=3&amp;hl=en_US
    """
    query = urlparse(yt_url)
    if query.hostname == "youtu.be" and ignore_playlist:
        return query.path[1:]
    if query.hostname in {
        "www.youtube.com",
        "youtube.com",
        "music.youtube.com",
        "m.youtube.com",
    }:
        if not ignore_playlist:
            # Use case: get playlist id, not current video in playlist
            with suppress(KeyError):
                return parse_qs(query.query)["list"][0]
            return None
        if query.path == "/watch":
            return parse_qs(query.query)["v"][0]
        if query.path[:7] == "/watch/":
            return query.path.split("/")[1]
        if query.path[:7] == "/embed/":
            return query.path.split("/")[2]
        if query.path[:3] == "/v/":
            return query.path.split("/")[2]
