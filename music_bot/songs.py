from config.config import Config
import asyncio
import discord
from discord.abc import GuildChannel
from discord.ext.commands import Bot, Context, UserInputError
import itertools
import os
from pytube import Playlist, Search, YouTube
import random
from spotify import is_spotify_url, SpotifyClientWrapper
from typing import Any
from unidecode import unidecode
import validators
import youtube

class Song:
    def __init__(self, video_id: str, music_path: str, ffmpeg_path: str):
        self.yt: YouTube = YouTube.from_id(video_id)
        self.music_path: str = music_path
        self.ffmpeg_path: str = ffmpeg_path
        self.file_name: str = f"{self.video_id}.mp3"
        self.file_path: str = os.path.join(self.music_path, self.file_name)
        self.formatted_duration: str = Song.format_duration(self.length)
        self.download_event: asyncio.Event = asyncio.Event()
        self.guilds_where_queued: set[int] = set()
        self.remove_event: asyncio.Event = asyncio.Event()
    
    @property
    def downloaded(self) -> bool:
        return self.download_event.is_set()

    @property
    def is_queued(self) -> bool:
        return not self.remove_event.is_set()
    
    @property
    def audio_source(self) -> discord.PCMVolumeTransformer:
        return discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(executable=self.ffmpeg_path, source=self.file_path))

    def __getattr__(self, __name: str) -> Any:
        return getattr(self.yt, __name)
    
    def download(self, after: function) -> None:
        self.yt.register_on_complete_callback(after)
        stream = self.yt.streams.filter(only_audio=True).first()
        stream.download(output_path=self.music_path, filename=self.file_name)
    
    @staticmethod
    def format_duration(duration: int):
        minutes, seconds = divmod(duration, 60)
        hours, minutes = divmod(minutes, 60)
        return f"{str(hours).zfill(2)}:{str(minutes).zfill(2)}:{str(seconds).zfill(2)}"

class SongRequest():
    def __init__(self, song: Song, requester: discord.Member, channel: GuildChannel, guild_id: int) -> None:
        self.song: Song = song
        self.requester: discord.Member = requester
        self.channel_where_requested: GuildChannel = channel
        self.guild_where_queued: int = guild_id
        self.guilds_where_queued.add(guild_id)
    
    def create_embed(self) -> discord.Embed:
        return (discord.Embed(title="Current song:",
                type="rich",
                description=f"[{self.title}]({self.watch_url})",
                color=discord.Color.blurple())
                .add_field(name="Duration", value=self.formatted_duration)
                .add_field(name="Requested by", value=self.requester.mention)
                .add_field(name="Uploader", value=f"[{self.author}]({self.channel_url})")
                .set_thumbnail(url=self.thumbnail_url))
    
    def __del__(self):
        print("Removing from guilds where queued")
        self.guilds_where_queued.remove(self.guild_where_queued)
        if not self.guilds_where_queued:
            self.remove_event.set()

    def __getattr__(self, __name):
        return getattr(self.song, __name)
    
    def __str__(self):
        return f"**{self.title}** by **{self.author}**"

class SongRequestQueue(asyncio.Queue):
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

    def put(self, item):
        super().put(item)
        
    def remove(self, index: int):
        del self._queue[index]

class SongFactory:
    def __init__(self, config: Config, bot: Bot) -> None:
        self.config: Config = config
        self.bot: Bot = bot
        self.ctx: Context = None
        self.encountered_songs: dict[str, Song] = dict()
        self.spotify_client_wrapper = SpotifyClientWrapper(config)

    def create_song_from_youtube_video(self, yt_video_url: str = None) -> list[Song]:
        yt_video_id = youtube.url_to_id(yt_video_url, ignore_playlist=True)
        song = self.encountered_songs.get(yt_video_id)
        if not song:
            song = Song(yt_video_id, self.config.music_path, self.config.ffmpeg_path)
            self.encountered_songs[yt_video_id] = song
        return song

    def create_song_from_youtube_search(self, search_query: str = None) -> list[Song]:
        search = Search(unidecode(search_query))
        if not search.results:
            asyncio.run_coroutine_threadsafe(self.ctx.send(f"YouTube search \"{search_query}\" did not yield any results. Ignoring and continuing."), loop=self.bot.loop)
        yt_video_url = search.results[0].watch_url
        return self.create_song_from_youtube_video(yt_video_url)

    def create_songs_from_youtube_playlist(self, yt_playlist_url: str = None) -> list[Song]:
        playlist = Playlist(yt_playlist_url)
        return [self.create_song_from_youtube_video(yt_video_url) for yt_video_url in playlist.video_urls]

    def create_songs_from_spotify(self, spotify_url: str = None) -> list[Song]:
        return [self.create_song_from_youtube_search(search_query) for search_query in self.spotify_client_wrapper.get_search_queries(spotify_url)]
    
    def create_song_requests(self, args: list[str]) -> list[SongRequest]:
        possible_url = args[0]
        songs = []
        if not validators.url(possible_url):
            search_query = " ".join(args)
            songs.append(self.create_song_from_youtube_search(search_query))
        elif youtube.is_video(possible_url):
            songs.append(self.create_song_from_youtube_video(possible_url))
        elif youtube.is_playlist(possible_url):
            songs.extend(self.create_songs_from_youtube_playlist(possible_url))
        elif is_spotify_url(possible_url):
            songs.extend(self.create_songs_from_spotify(possible_url))
        else:
            raise UserInputError(f"Argument {possible_url} is structured like a url but is not a valid YouTube or Spotify url.")
            
        return [SongRequest(song, self.ctx.message.author, self.ctx.guild.id) for song in songs]