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
from discord.ext.commands import Bot, Context
from .music_database import MusicDatabase
from .utils import format_time_str
from .youtube import YoutubeVideo

class Stats:
    def __init__(self, embed_title: str, embed_fields: dict[str, str]) -> None:
        self.embed_title = embed_title
        self.embed_fields: dict[str, str] = embed_fields
    
    def create_main_embed(self) -> discord.Embed:
        embed = discord.Embed(title=self.embed_title, color=discord.Color.random())
        for name, value in self.embed_fields.values():
            embed.add_field(name=name, value=value)
        return embed

class SongStats(Stats):
    def __init__(self, yt_video: YoutubeVideo, stats: dict[str, str]) -> None:
        embed_title = f"Stats for [{yt_video.title}]({yt_video.video_url})"
        stats["Duration"] = yt_video.duration
        super().__init__(embed_title, stats)

class UserStats(Stats):
    def __init__(self, user: discord.Member, stats: dict[str, str]) -> None:
        embed_title = f"Stats for {user.mention}"
        super().__init__(embed_title, stats)

class StatsFactory:
    def __init__(self, music_db: MusicDatabase) -> None:
        self.music_db: MusicDatabase = music_db
        self.ctx: Context = None
    
    async def create_stats(
        self, ctx: Context, *,
        user: discord.Member = None,
        yt_search_query: str = None,
        yt_video_url: str = None) -> Stats:
        self.ctx = ctx
        if yt_search_query or yt_video_url:
            stats = await self.create_song_stats(yt_search_query=yt_search_query, yt_video_url=yt_video_url)
        elif user:
            stats = await self.create_user_stats(user)
        else:
            stats = await self.create_server_stats()
        return stats
    
    async def create_song_stats(self, yt_search_query: str = None, yt_video_url: str = None) -> Stats:
        if yt_search_query:
            yt_video = await YoutubeVideo.from_search_query(yt_search_query)
        else:
            yt_video = await YoutubeVideo.from_url(yt_video_url)
        stats = dict()
        song_requests = await self.music_db.get_song_requests(self.ctx.guild.id, song_id=yt_video.video_id)
        song_plays = await self.music_db.get_song_plays(self.ctx.guild.id, song_id=yt_video.video_id)
        stats["Times Requested"] = len(song_requests)
        stats["Times Played"] = len(song_plays)
        stats["Total Time Played"] = format_time_str(sum([song_play.duration for song_play in song_plays]))
        counts = dict()
        for song_request in song_requests:
            counts[song_request.requester_id] = counts.get(song_request.requester_id, 0) + 1
        best_requester_id = max(counts, key=lambda requester: counts[requester])
        best_requester = self.ctx.guild.get_member(best_requester_id)
        stats["Most Frequent Requester"] = f"{best_requester.mention} with {counts[best_requester_id]} requests"
        return SongStats(yt_video, stats)

    async def create_user_stats(self, user: discord.Member) -> Stats:
        stats = dict()
        song_requests = await self.music_db.get_song_requests(self.ctx.guild.id, requester_id=user.id)
        song_plays = await self.music_db.get_song_plays(self.ctx.guild.id, requester_id=user.id)
        stats["Requests Made"] = len(song_requests)
        stats["Requested Songs Played"] = len(song_plays)
        stats["Total Time Requested Songs Played"] = format_time_str(sum([song_play.duration for song_play in song_plays]))
        counts = dict()
        for song_request in song_requests:
            counts[song_request.song_id] = counts.get(song_request.song_id, 0) + 1
        best_song_id = max(counts, key=lambda song_id: counts[song_id])
        yt_video = await YoutubeVideo.from_id(best_song_id)
        best_song_title = yt_video.title
        stats["Most Requested Song"] = f"{best_song_title} with {counts[best_song_id]} requests"
        return UserStats(user, stats)
    
    async def create_server_stats(self) -> Stats:
        stats = dict()
        song_requests = await self.music_db.get_song_requests(self.ctx.guild.id)
        song_plays = await self.music_db.get_song_plays(self.ctx.guild.id)
        stats["Total Requests"] = len(song_requests)
        stats["Total Songs Played"] = len(song_plays)
        stats["Total Time Played"] = format_time_str(sum([song_play.duration for song_play in song_plays]))
        song_counts = dict()
        requester_counts = dict()
        for song_request in song_requests:
            song_counts[song_request.song_id] = song_counts.get(song_request.song_id, 0) + 1
            requester_counts[song_request.requester_id] = requester_counts.get(song_request.requester_id, 0) + 1
        best_song_id = max(song_counts, key=lambda song_id: song_counts[song_id])
        yt_video = await YoutubeVideo.from_id(best_song_id)
        best_song_title = yt_video.title
        best_requester_id = max(requester_counts, key=lambda requester_id: requester_counts[requester_id])
        best_requester = self.ctx.message.guild.get_member(best_requester_id)
        stats["Most Requested Song"] = f"{best_song_title} with {song_counts[best_song_id]} requests"
        stats["Most Frequent Requester"] = f"{best_requester.mention} with {requester_counts[best_requester_id]} requests"
        embed_title = f"Server Stats for {self.ctx.guild.name}"
        return Stats(embed_title, stats)
