import asyncio
from config.config import Config
from datetime import datetime, timedelta
import discord
from discord.abc import Guild, GuildChannel
from discord.ext.commands import Context
import itertools
import math
import music_database
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

    def __init__(self, config: Config, yt_video: YoutubeVideo, ctx: Context) -> None:
        self.config: Config = config
        self.yt_video: YoutubeVideo = yt_video
        self.guild: Guild = ctx.guild
        self.requester: discord.Member = ctx.author
        self.channel_where_requested: GuildChannel = ctx.channel
        self.timestamp_requested: datetime = datetime.now()
        self.timestamp_last_played: datetime = None
        self.time_played: timedelta = timedelta()

    @property
    def audio_source(self) -> discord.FFmpegOpusAudio:
        return discord.FFmpegOpusAudio(source=self.stream_url, **self.FFMPEG_OPTIONS)
    
    @property
    def duration_played(self) -> float:
        if not self.timestamp_last_played:
            return 0.0
        end_timestamp = self.timestamp_last_stopped or datetime.now()
        duration = end_timestamp - self.duration_last_played
        return duration.seconds

    @property
    def song_request(self) -> music_database.SongRequest:
        return music_database.SongRequest(
            timestamp=self.timestamp_requested,
            guild_id=self.guild.id,
            requester_id=self.requester.id,
            song_id=self.video_id)
    
    @property
    def song_play(self) -> music_database.SongPlay:
        return music_database.SongPlay(
            timestamp=self.timestamp_requested,
            guild_id=self.guild.id,
            requester_id=self.requester.id,
            song_id=self.video_id,
            duration=self.duration_last_played)
    
    def create_embed(self) -> discord.Embed:
        return (discord.Embed(title="Current song:",
                type="rich",
                description=self.video_link_markdown,
                color=discord.Color.random())
                .add_field(name="Duration", value=self.formatted_duration)
                .add_field(name="Requested by", value=self.requester.mention)
                .add_field(name="Uploader", value=self.channel_link_markdown)
                .set_thumbnail(url=self.thumbnail_url))

    def record_stop(self):
        if self.timestamp_last_played:
            end_timestamp = datetime.now()
            delta = end_timestamp - self.timestamp_last_played
            self.time_played += delta
            self.timestamp_last_played = None

    def __str__(self):
        return f":notes: **{self.title}** :notes: by **{self.channel_name}**"
    
    def __getattr__(self, __name) -> Any:
        return getattr(self.yt_video, __name)

# TODO: add discord embed of queue to object, maybe with page argument
class SongQueue(asyncio.Queue):
    def __init__(self, max_shown_songs: int):
        self.max_shown_songs: int = max_shown_songs
        super().__init__()
    
    def create_embed(self, page: int) -> discord.Embed:
        pages = math.ceil(len(self._queue) / self.max_shown_songs)

        start = (page - 1) * self.max_shown_songs
        end = start + self.max_shown_songs

        queue_str = ""
        for i, song in enumerate(self._queue[start:end], start=start):
            queue_str += f"`{i + 1}.`  [**{song.title}**]({song.video_url})\n"

        embed_title = f"**Song queue has {len(self._queue)} track{'s' if len(self._queue) > 1 else ''}**:"
        embed = (discord.Embed(title=embed_title,
                description=queue_str,
                color=discord.Color.random()
                ).set_footer(text=f"Viewing page {page}/{pages}"))
        return embed
    
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
    def __init__(self, config: Config, music_db: music_database.MusicDatabase) -> None:
        self.config: Config = config
        self.music_db: music_database.MusicDatabase = music_db
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
        song = Song(self.config, yt_video, self.ctx)
        await self.music_db.insert_data(song.song_request)
        return song