"""
Contains classes used to retrieve and store YouTube data using yt-dlp.
"""

import asyncio
import functools
import time
from typing import Any, override

from yt_dlp import YoutubeDL
from yt_dlp.utils import YoutubeDLError

from config import Config

from .utils import format_time_str, get_link_markdown


class YtdlSource:
    """Class to store YouTube data retrieved with yt-dlp.

    YouTube videos and playlists have shared fields in the data retrieved by yt-dlp,
    so this class is used to store them. These shared fields only contain basic metadata
    for the source playlist or video, and cannot be used to stream audio.

    Attributes:
        id: A string containing the id of the video or playlist. Ex: "dQw4w9WgXcQ"
        url: A string containing the url of the video or playlist. Ex: "https://youtu.be/dQw4w9WgXcQ"
        title: A string containing the title of the video or playlist.
            Ex: "Rick Astley - Never Gonna Give You Up (Official Music Video)"
        link_markdown: A string containing a hyperlink to the YouTube video or playlist in markdown,
            using the title and url.
            Ex: "[Rick Astley - Never Gonna Give You Up (Official Music Video)](https://youtu.be/dQw4w9WgXcQ)"
        uploader_name: A string containing the uploader (YouTube channel name) of the video or playlist.
            Ex: "Rick Astley"
        uploader_url: A string containing the YouTube channel url of the video or playlist.
            Ex: "https://www.youtube.com/channel/UCuAXFkgsw1L7xaCfnd5JJOw"
        uploader_link_markdown: A string containing a hyperlink to the channel of the video or playlist,
            using the channel name and url.
        description: A string containing the description of the video or plalist.
            Ex: "The official video for “Never Gonna Give You Up” by Rick Astley..."
    """

    def __init__(self, ytdl_data: dict[str, Any]) -> None:
        """Initializes the instance based on YouTube data retrieved from yt-dlp.

        Args:
            ytdl_data: A dictionary containing YouTube data retrieved from yt-dlp.
        """
        self.id: str = ytdl_data.get("id")
        self.url: str = ytdl_data.get("webpage_url") or ytdl_data.get("url")
        self.title: str = ytdl_data.get("title")
        self.link_markdown: str = get_link_markdown(self.title, self.url)

        self.uploader_name: str = ytdl_data.get("channel") or ytdl_data.get("uploader")
        self.uploader_url: str = ytdl_data.get("channel_url") or ytdl_data.get(
            "uploader_url"
        )
        self.uploader_link_markdown: str = (
            get_link_markdown(self.uploader_name, self.uploader_url)
            if self.uploader_url
            else self.uploader_name
        )

        self.description: str = ytdl_data.get("description")


class YtdlVideoSource(YtdlSource):
    """Class to store YouTube video data retrieved with yt-dlp.

    Stores additional data for YouTube videos only available after processing them with yt-dlp.
    Can be processed with an instance method, and tracks if the current instance has been processed yet
    using an async event. Instances of this class must be processed for them to be a valid audio source for streaming.

    Attributes:
        is_processed: A boolean indicating if this YouTube video has been processed by yt-dlp yet.
        thumbnail_url: A string containing the thumbnail url of the YouTube video. None if not processed.
        duration: An integer containing the duration of the video, in seconds. None if not processed.
        formatted_duration: A string containing the duration of the video, in "hh:mm:ss" format. None if not processed.
        stream_url: A string containing the stream url of the video. None if not processed.
            This will be used later to stream audio to discord. None if not processed.
    """

    @override
    def __init__(self, ytdl_data: dict[str, Any]) -> None:
        super().__init__(ytdl_data)

        # Processed video data from yt-dlp will not have a "_type" key.
        # Unprocessed video data will have a "_type" of "url".
        self.is_processed: bool = ytdl_data.get("_type") != "url"
        if self.is_processed:
            self.process(ytdl_data)

    def process(self, processed_ytdl_data: dict[str, Any]) -> None:
        """Populates additional fields only available after processing YouTube video data.

        Used to process the current instance if it was not already instantiated with processed data from yt-dlp.

        Args:
            processed_ytdl_data: A dictionary containing processed YouTube data retrieved from yt-dlp.
        """
        self.thumbnail_url: str = processed_ytdl_data.get("thumbnail")
        self.duration: int = processed_ytdl_data.get("duration")
        self.formatted_duration: str = format_time_str(self.duration)
        self.stream_url: str = processed_ytdl_data.get("url")


class YtdlPlaylistSource(YtdlSource):
    """Class to store YouTube playlist data retrieved with yt-dlp.

    Stores additional data for YouTube playlists.

    Attributes:
        thumbnail_url: A string containing the thumbnail url of the playlist.
        video_count: An integer count of the videos in the playlist. Note that this count will be different from
            len(self.video_sources) if there's an error processing any videos in the playlist.
        video_sources: A list of YtdlVideoSource objects representing the videos in the playlist.
        are_videos_processed: A boolean indicating if the video sources in the playlist have been processed or not.
    """

    def __init__(
        self, ytdl_data: dict[str, Any], video_sources: list[YtdlVideoSource]
    ) -> None:
        """Initializes the instance based on YouTube playlist data retrieved from yt-dlp.

        Args:
            ytdl_data: A dictionary containing YouTube playlist data retrieved from yt-dlp.
            video_sources: a list of YtdlVideoSource objectsrepresenting the videos in the playlist.
        """
        super().__init__(ytdl_data)

        highest_resolution_thumbnail = max(
            ytdl_data.get("thumbnails"),
            key=lambda thumbnail: thumbnail.get("height") * thumbnail.get("width"),
        )
        self.thumbnail_url: str = highest_resolution_thumbnail.get("url")
        self.video_count: int = ytdl_data.get("playlist_count")

        self.video_sources: list[YtdlVideoSource] = video_sources
        self.are_videos_processed: bool = all(
            [video_source.is_processed for video_source in video_sources]
        )


class YtdlSourceFactory:
    """Class to create and process YtdlSource objects with YouTube data retrieved from yt-dlp.

    Handles all interaction with yt-dlp and wraps calls with additional logic, such as retries.
    Creates and processes YtdlSource objects for data retrieved from yt-dlp, with different logic for
    different types of input, such as a YouTube search query, YouTube video id or url, or YouTube playlist url.

    Attributes:
        config: A Config object representing the configuration of the music bot.
    """

    YTDL_OPTIONS = {
        "format": "bestaudio[acodec=opus]/bestaudio/best",
        "extractaudio": True,
        "extract_flat": False,
        "audioformat": "opus",
        "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
        "restrictfilenames": True,
        "noplaylist": True,
        "nocheckcertificate": True,
        "ignoreerrors": True,
        "logtostderr": False,
        "quiet": True,
        "no_warnings": True,
        "default_search": "auto",
        "source_address": "0.0.0.0",
        "skip_download": True,
    }

    def __init__(self, config: Config) -> None:
        """Initializes the current instance based on the music bot config.

        Args:
            config: A Config object representing the configuration of the music bot.
        """
        self.config: Config = config

    async def process_ytdl_video_source(
        self, ytdl_video_source: YtdlVideoSource
    ) -> None:
        """Processes an existing YtdlVideoSource object with processed data retrieved from yt-dlp.

        Args:
            ytdl_video_source: The YtdlVideoSource object to process.
        """
        processed_ytdl_data = await self.extract_ytdl_data_with_retry(
            ytdl_video_source.id, download=False, process=True
        )
        ytdl_video_source.process(processed_ytdl_data)

    async def create_ytdl_video_source(
        self, ytdl_args: str, is_yt_search: bool = False
    ) -> YtdlVideoSource:
        """Creates a YtdlVideoSource object based on a YouTube video url or search.

        Args:
            ytdl_args: A string containing a YouTube video url or search query.
            is_yt_search: A boolean indicating whether or not ytdl_args is a YouTube search query.

        Returns:
            The created YtdlVideoSource object.
        """
        if is_yt_search:
            ytdl_args = "ytsearch:" + ytdl_args
        ytdl_data = await self.extract_ytdl_data_with_retry(
            ytdl_args, download=False, process=True
        )
        if is_yt_search:
            ytdl_data = ytdl_data["entries"][0]
        ytdl_video_source = YtdlVideoSource(ytdl_data)
        return ytdl_video_source

    async def create_ytdl_playlist_source(
        self, yt_playlist_url: str
    ) -> YtdlPlaylistSource:
        """Creates a YtdlPlaylistSource object based on a YouTube playlist url.

        Args:
            yt_playlist_url: A string containing a YouTube playlist url.

        Returns:
            The created YtdlPlaylistSource.
        """
        ytdl_data = await self.extract_ytdl_data_with_retry(
            yt_playlist_url, download=False, process=False
        )
        ytdl_video_sources = [YtdlVideoSource(entry) for entry in ytdl_data["entries"]]
        ytdl_playlist_source = YtdlPlaylistSource(ytdl_data, ytdl_video_sources)
        return ytdl_playlist_source

    async def extract_ytdl_data_with_retry(
        self, *args: tuple, max_tries=3, retry_interval_sec=5, **kwargs: dict[str, Any]
    ) -> dict[str, Any]:
        """Extracts YouTube data using yt-dlp extract_info() method, with retry logic.

        Args:
            *args: Tuple of arguments to pass to extract_info() method.
            max_tries: Integer representing the how many times to try calling extract_info() before giving up.
                Defaults to 3.
            retry_interval_sec: Integer representing how long to wait between retries, in seconds. Defaults to 5.
            **kwargs: Dictionary of keyword arguments to pass to extract_info() method.

        Returns:
            A dictionary of YouTube data retrieved from yt-dlp.
        """
        ytdl = YoutubeDL(self.YTDL_OPTIONS)

        tries, ytdl_data = 0, None
        while not ytdl_data and tries < max_tries:
            try:
                print(f"Extracting info for try {tries + 1}")
                self.start = time.time()
                partial_func = functools.partial(ytdl.extract_info, *args, **kwargs)
                ytdl_data = await asyncio.get_running_loop().run_in_executor(
                    None, partial_func
                )
                end = time.time()
                time_span = end - self.start
                print(
                    f"Are we blocking here in extract_info? It took {time_span} seconds."
                )
            except YoutubeDLError as e:
                print(f"Encountered YTDL error on try {tries + 1} of {max_tries}: {e}")
                await asyncio.sleep(retry_interval_sec)
            except Exception as e:
                print(f"Encountered exception on try {tries + 1} of {max_tries}: {e}")
                await asyncio.sleep(retry_interval_sec)

            tries += 1

        if not ytdl_data:
            msg = f"Failed to get data from YTDL after {tries} tries for argument: {args[0]}."
            print(msg)
            raise YoutubeDLError(msg)
        else:
            print(f"extracted info on try {tries}")

        return ytdl_data
