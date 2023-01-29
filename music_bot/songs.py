import asyncio
from config.config import Config
from datetime import datetime
import discord
from discord.abc import GuildChannel
from discord.ext.commands import Context
import itertools
import random
from .spotify import SpotifyClientWrapper
import traceback
from typing import Any
from .youtube import YoutubePlaylist, YoutubeVideo

class Song:
    FFMPEG_OPTIONS = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn',
    }

    def __init__(self, config: Config, yt_video: YoutubeVideo, requester: discord.Member, channel: GuildChannel) -> None:
        self.config: Config = config
        self.yt_video: YoutubeVideo = yt_video
        self.requester: discord.Member = requester
        self.channel_where_requested: GuildChannel = channel
        self.timestamp_requested: datetime = datetime.now()
        self.timestamp_last_played: datetime = None
        self.timestamp_last_stopped: datetime = None

    @property
    def audio_source(self) -> discord.FFmpegOpusAudio:
        return discord.FFmpegOpusAudio(source=self.stream_url, **Song.FFMPEG_OPTIONS)
    
    @property
    def duration_last_played(self) -> int:
        if not self.timestamp_last_played:
            return 0
        end_timestamp = self.timestamp_last_stopped or datetime.now()
        duration = end_timestamp - self.duration_last_played
        return duration.seconds
    
    # @property
    # def song_csv_row(self) -> list[str]:
    #     return [self.video_id, self.title, self.channel_name, self.duration]

    # @property
    # def request_csv_row(self) -> list[str]:
    #     return [str(self.requester.id), self.video_id, str(self.timestamp_requested)]
    
    # @property
    # def play_csv_row(self) -> list[str]:
    #     return [str(self.requester.id), self.video_id, str(self.timestamp_last_played), str(self.duration_last_played)]
    
    def create_embed(self) -> discord.Embed:
        return (discord.Embed(title="Current song:",
                type="rich",
                description=f"[{self.title}]({self.video_url})",
                color=discord.Color.random())
                .add_field(name="Duration", value=self.formatted_duration)
                .add_field(name="Requested by", value=self.requester.mention)
                .add_field(name="Uploader", value=f"[{self.channel_name}]({self.channel_url})")
                .set_thumbnail(url=self.thumbnail_url))
    
    # async def write_song(self):
    #     await write_to_csv(self.config.songs_file_path, self.song_csv_row)

    # async def write_song_request(self) -> None:
    #     await write_to_csv(self.config.song_requests_file_path, self.request_csv_row)
    
    # async def write_song_play(self) -> None:
    #     await write_to_csv(self.config.song_plays_file_path, self.play_csv_row)

    def __str__(self):
        return f":notes: **{self.title}** :notes: by **{self.channel_name}**"
    
    def __getattr__(self, __name) -> Any:
        return getattr(self.yt_video, __name)

class SongQueue(asyncio.Queue):
    def __getitem__(self, item):
        if isinstance(item, slice):
            return list(itertools.islice(self._queue, item.start, item.stop, item.step))
        else:
            return self._queue[item]

    def __bool__(self):
        return len(self._queue) > 0

    def __iter__(self):
        return self._queue.__iter__()

    def __len__(self):
        return self.qsize()

    def clear(self):
        self._queue.clear()

    def shuffle(self):
        random.shuffle(self._queue)
        
    def remove(self, index: int):
        del self._queue[index]

class SongFactory:
    def __init__(self, config: Config) -> None:
        self.config: Config = config
        self.ctx: Context = None
        self.spotify_client_wrapper = SpotifyClientWrapper(config)
    
    async def create_songs(
            self, ctx: Context, *,
            yt_search_query: str = None,
            yt_video_urls: list[str] = [],
            yt_playlist_urls: list[str] = [],
            spotify_urls: list[str] = []) -> list[Song]:
        self.ctx = ctx
        songs = []
        print("about to create song")
        songs.append(await self.create_song_from_yt_search(yt_search_query))
        songs.extend(await self.create_songs_from_yt_video_urls(yt_video_urls))
        songs.extend(await self.create_songs_from_yt_playlist_urls(yt_playlist_urls))
        songs.extend(await self.create_songs_from_spotify_urls(spotify_urls))
        print("got song requests, returning")
        return [song for song in songs if song]
    
    async def create_songs_from_yt_playlist_urls(self, yt_playlist_urls: list[str]) -> list[Song]:
        tasks = [self.create_songs_from_yt_playlist_url(yt_playlist_url) for yt_playlist_url in yt_playlist_urls]
        song_lists = await asyncio.gather(*tasks, return_exceptions=True)
        for p in song_lists:
            if isinstance(p, Exception):
                traceback.print_exception(p)
        return [song for song_list in song_lists for song in song_list]
    
    async def create_songs_from_yt_playlist_url(self, yt_playlist_url: str) -> list[Song]:
        yt_playlist = await YoutubePlaylist.from_url(yt_playlist_url)
        return [await self.create_song(yt_video) for yt_video in yt_playlist.videos]

    async def create_songs_from_spotify_urls(self, spotify_urls: list[str]) -> list[Song]:
        tasks = [self.create_songs_from_spotify_url(spotify_url) for spotify_url in spotify_urls]
        song_lists = await asyncio.gather(*tasks, return_exceptions=True)
        for p in song_lists:
            if isinstance(p, Exception):
                traceback.print_exception(p)
            print(p)
        return [song for song_list in song_lists for song in song_list]
    
    async def create_songs_from_spotify_url(self, spotify_url: str) -> list[Song]:
        search_queries = await self.spotify_client_wrapper.get_search_queries(spotify_url)
        if not search_queries:
            await self.ctx.send(f"Spotify url \"{spotify_url}\" did not yield any results.")
        tasks = [self.create_song_from_yt_search(search_query) for search_query in search_queries]
        return await asyncio.gather(*tasks, return_exceptions=True)

    async def create_song_from_yt_search(self, yt_search_query: str) -> Song:
        yt_video = await YoutubeVideo.from_search_query(yt_search_query)
        if yt_search_query and not yt_video:
            await self.ctx.send(f"Youtube search \"{yt_search_query}\" did not yield any results.")
        return await self.create_song(yt_video)

    async def create_songs_from_yt_video_urls(self, yt_video_urls: list[str]) -> list[Song]:
        tasks = [self.create_song_from_yt_video_url(yt_video_url) for yt_video_url in yt_video_urls]
        songs = await asyncio.gather(*tasks, return_exceptions=True)
        for song in songs:
            if not isinstance(song, Song):
                print("NOT A SONG:", song)
        return songs
    
    async def create_song_from_yt_video_url(self, yt_video_url: str) -> Song:
        yt_video = await YoutubeVideo.from_url(yt_video_url)
        if not yt_video:
            await self.ctx.send(f"Youtube video at \"{yt_video_url}\" is not available.")
        return await self.create_song(yt_video)

    async def create_song(self, yt_video: YoutubeVideo) -> Song:
        if not yt_video:
            return None
        song = Song(yt_video, self.ctx.message.author, self.ctx.channel)
        # await song.write_song()
        # await song.write_song_request()
        return song