# import os
# import pandas as pd

# class Stats:
#     def __init__(self, data_dir: str):
#         self.data_dir: str = data_dir
#         self.songs_file: str = os.path.join(data_dir, "songs.csv")
#         self.song_requests_file: str = os.path.join(data_dir, "song_requests.csv")

#     def calculate_song_stats(song_info):
#         s = Search(unidecode(song_info))
#         if len(s.results) == 0: # No results for search
#             return None
#         yt = s.results[0]
#         id = yt.video_id
#         if id not in song_data:
#             return None

#         data = song_data[id]
#         song_stats = {}

#         # Title
#         song_stats["Title"] = data["title"]

#         # Duration
#         song_stats["Duration"] = time_string(data["duration"])

#         # Request Count
#         song_stats["Request count"] = data["request count"]

#         # Times played
#         song_stats["Times played"] = data["times played"]

#         return song_stats   

#     def read_songs(self):
#         return pd.read_csv(self.songs_file)

#     def read_song_requests(self):
#         return pd.read_csv(self.song_requests_file)
    
#     def write_song(self, song: list[str]):
#         write_to_csv(self.song_requests_file, song)
    
#     def write_song_request(self, song_request: list[str]):
#         write_to_csv(self.song_requests_file, song_request)
import discord
from discord.ext.commands import Context
from .music_database import MusicDatabase, SongRequest, SongPlay
from .youtube import YoutubeVideo

class Stats:
    def __init__(self, embed_title: str, embed_fields: dict[str, str]) -> None:
        self.embed_title = embed_title
        self.embed_fields: dict[str, str] = embed_fields
    
    def create_embed(self) -> discord.Embed:
        embed = discord.Embed(title=self.embed_title, color=discord.Color.random())
        for name, value in self.embed_fields.values():
            embed.add_field(name=name, value=value)
        return embed

class SongStats(Stats):
    def __init__(self, yt_video: YoutubeVideo, stats: dict[str, str]) -> None:
        embed_title = f"Stats for [{yt_video.title}]({yt_video.video_url})"
        stats["Duration"] = yt_video.duration
        super().__init__(embed_title, stats)

class StatsFactory:
    def __init__(self, music_db: MusicDatabase) -> None:
        self.music_db: MusicDatabase = music_db
        self.ctx: Context = None
        self.song_attributes: list[str] = ["title", "", "channel_name", "channel_url" "duration"]
    
    async def create_stats(
        self, ctx: Context, *,
        user: discord.Member = None,
        yt_search_query: str = None,
        yt_video_url: str = None) -> Stats:
        if requester_id:
            embed_title = f""
    
    async def create_song_stats(yt_search_query: str = None, yt_video_url: str = None) -> Stats:
        stats_dict = dict()
        if yt_search_query:
            yt_video = await YoutubeVideo.from_search_query(yt_search_query)
            stats_dict["title"] = yt_video.title
            stats_dict["title"] = yt_video.title
            stats_dict["title"] = yt_video.title
            stats_dict["title"] = yt_video.title
