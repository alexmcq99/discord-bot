
import asyncio
from config.config import Config
from discord.ext.commands import Bot, CommandError, Context
from pytube import Playlist, Search, YouTube
from pytube.exceptions import VideoUnavailable
from songs import Song, SongRequest
from spotify import is_spotify_url, SpotifyClientWrapper
from unidecode import unidecode
import validators
import youtube

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
            asyncio.run_coroutine_threadsafe(self.ctx.send(f"YouTube search \"{search_query}\" did not yield any results, ignoring and continuing."), loop=self.bot.loop)
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
            songs.append(self.song_factory.create_song_from_youtube_search(search_query))
        elif youtube.is_video(possible_url):
            songs.append(self.song_factory.create_song_from_youtube_video(possible_url))
        elif youtube.is_playlist(possible_url):
            songs = self.song_factory.create_songs_from_youtube_playlist(possible_url)
        elif is_spotify_url(possible_url):
            songs = self.song_factory.create_songs_from_spotify(possible_url)
        else:
            raise CommandError(f"Argument {possible_url} is structured like a url but is not a valid YouTube or Spotify url.")
            
        return [SongRequest(song, self.ctx.message.author, self.ctx.guild.id) for song in songs]