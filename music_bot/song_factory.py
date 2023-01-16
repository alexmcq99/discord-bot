
import asyncio
from config.config import Config
from discord.ext.commands import Bot, CommandError, Context
from pytube import Playlist, Search
from .songs import Song
from .spotify import is_spotify_url, SpotifyClientWrapper
from unidecode import unidecode
import validators
from .youtube import is_video, is_playlist, url_to_id

class SongFactory:
    def __init__(self, config: Config, bot: Bot) -> None:
        self.config: Config = config
        self.bot: Bot = bot
        self.ctx: Context = None
        print("song factory init")
        self.spotify_client_wrapper = SpotifyClientWrapper(config)

    def create_song_from_youtube_video(self, yt_video_url: str = None) -> Song:
        yt_video_id = url_to_id(yt_video_url, ignore_playlist=True)
        song = Song(yt_video_id, self.ctx.author, self.ctx.channel, self.config.ffmpeg_path)
        return song

    def create_song_from_youtube_search(self, search_query: str = None) -> Song:
        search = Search(unidecode(search_query))
        if not search.results:
            asyncio.run_coroutine_threadsafe(self.ctx.send(f"YouTube search \"{search_query}\" did not yield any results, ignoring and continuing."), loop=self.bot.loop)
            return None
        yt_video_url = search.results[0].watch_url
        return self.create_song_from_youtube_video(yt_video_url)

    def create_songs_from_youtube_playlist(self, yt_playlist_url: str = None) -> list[Song]:
        playlist = Playlist(yt_playlist_url)
        return [self.create_song_from_youtube_video(yt_video_url) for yt_video_url in playlist.video_urls]

    def create_songs_from_spotify(self, spotify_url: str = None) -> list[Song]:
        return [self.create_song_from_youtube_search(search_query) for search_query in self.spotify_client_wrapper.get_search_queries(spotify_url)]
    
    def create_songs(self, args: list[str]) -> list[Song]:
        possible_url = args[0]
        songs = []
        if not validators.url(possible_url):
            search_query = " ".join(args)
            songs.append(self.create_song_from_youtube_search(search_query))
        elif is_video(possible_url):
            songs.append(self.create_song_from_youtube_video(possible_url))
        elif is_playlist(possible_url):
            songs = self.create_songs_from_youtube_playlist(possible_url)
        elif is_spotify_url(possible_url):
            songs = self.create_songs_from_spotify(possible_url)
        else:
            raise CommandError(f"Argument {possible_url} is structured like a url but is not a valid YouTube or Spotify url.")
        return songs