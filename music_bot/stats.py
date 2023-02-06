import discord
from discord.ext.commands import Context
from .usage_database import UsageDatabase, SongRequest
from .time_utils import format_datetime, format_time_str
from typing import Any, Optional
from .youtube import YoutubeVideo

class Stats:
    def __init__(self, embed_title: str, embed_description: str, thumbnail_url: str, stats: dict[str, str]) -> None:
        self.embed_title: str = embed_title
        self.embed_description: str = embed_description
        self.thumbnail_url: str = thumbnail_url
        self.stats: dict[str, str] = stats
    
    def create_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=self.embed_title, 
            color=discord.Color.random(),
            description=self.embed_description
        )
        embed.set_thumbnail(url=self.thumbnail_url)
        for name, value in self.stats.items():
            embed.add_field(name=name, value=value)
        return embed

class ServerStats(Stats):
    def __init__(self, guild: discord.Guild, stats: dict[str, str]) -> None:
        embed_title = "Stats for Server:"
        embed_description = guild.name
        thumbnail_url = guild.icon.url
        super().__init__(embed_title, embed_description, thumbnail_url, stats)

class UserStats(Stats):
    def __init__(self, user: discord.Member, stats: dict[str, str]) -> None:
        embed_title = "Stats for User:"
        embed_description =  user.mention
        thumbnail_url = user.avatar.url
        super().__init__(embed_title, embed_description, thumbnail_url, stats)

class SongStats(Stats):
    def __init__(self, yt_video: YoutubeVideo, stats: dict[str, str]) -> None:
        embed_title = "Stats for Song:"
        embed_description = yt_video.video_link_markdown
        thumbnail_url = yt_video.thumbnail_url
        stats["Duration"] = yt_video.formatted_duration
        super().__init__(embed_title, embed_description, thumbnail_url, stats)

class UserSongStats(Stats):
    def __init__(self, user: discord.Member, yt_video: YoutubeVideo, stats: dict[str, str]) -> None:
        embed_title = f"Stats for {user.mention} with {yt_video.video_link_markdown})"
        thumbnail_url = user.avatar.url
        stats["Duration"] = yt_video.formatted_duration
        super().__init__(embed_title, thumbnail_url, stats)

class StatsFactory:
    def __init__(self, usage_db: UsageDatabase) -> None:
        self.usage_db: UsageDatabase = usage_db
        self.ctx: Context = None
    
    async def create_stats(
            self, ctx: Context, *,
            user: Optional[discord.Member] = None,
            yt_search_query: Optional[str] = None,
            yt_video_url: Optional[str] = None) -> Stats:
        
        self.ctx = ctx
        filter_kwargs = {
            "guild_id": ctx.guild.id
        }
        if user and (yt_search_query or yt_video_url):
            stats = await self.create_user_song_stats(filter_kwargs, user, yt_search_query=yt_search_query, yt_video_url=yt_video_url)
        elif user:
            stats = await self.create_user_stats(filter_kwargs, user)
        elif yt_search_query or yt_video_url:
            stats = await self.create_song_stats(filter_kwargs, yt_search_query=yt_search_query, yt_video_url=yt_video_url)
        else:
            stats = await self.create_server_stats(filter_kwargs)
        return stats

    async def create_server_stats(self, filter_kwargs: dict[str, Any]) -> ServerStats:
        stats = {
            "Total Requests": await self.usage_db.get_song_request_count(filter_kwargs),
            "Total Songs Played": await self.usage_db.get_song_play_count(filter_kwargs),
            "First Request": await self.format_request_for_server(await self.usage_db.get_first_request(filter_kwargs)),
            "Most Recent Request": await self.format_request_for_server(await self.usage_db.get_latest_request(filter_kwargs)),
            "Total Time Played": format_time_str(await self.usage_db.get_total_play_duration(filter_kwargs)),
            "Most Frequent Requester": await self.get_most_frequent_requester_formatted(filter_kwargs),
            "Most Requested Song": await self.get_most_requested_song_formatted(filter_kwargs)
        }
        server_stats = ServerStats(self.ctx.guild, stats)
        return server_stats

    async def create_user_stats(self, filter_kwargs: dict[str, Any], user: discord.Member) -> UserStats:
        filter_kwargs["requester_id"] = user.id
        stats = {
            "Requests Made": await self.usage_db.get_song_request_count(filter_kwargs),
            "Requested Songs Played": await self.usage_db.get_song_play_count(filter_kwargs),
            "First Request": await self.format_request_for_user(await self.usage_db.get_first_request(filter_kwargs)),
            "Most Recent Request": await self.format_request_for_user(await self.usage_db.get_latest_request(filter_kwargs)),
            "Total Time Requested Songs Played": format_time_str(await self.usage_db.get_total_play_duration(filter_kwargs)),
            "Most Requested Song": await self.get_most_requested_song_formatted(filter_kwargs)
        }
        user_stats = UserStats(user, stats)
        return user_stats
    
    async def create_song_stats(
            self, 
            filter_kwargs: dict[str, Any], 
            yt_search_query: Optional[str] = None, 
            yt_video_url: Optional[str] = None) -> SongStats:
        
        if yt_search_query:
            yt_video = await YoutubeVideo.from_search_query(yt_search_query)
        else:
            yt_video = await YoutubeVideo.from_url(yt_video_url)
        
        filter_kwargs["song_id"] = yt_video.video_id

        stats = {
            "Times Requested": await self.usage_db.get_song_request_count(filter_kwargs),
            "Times Played": await self.usage_db.get_song_play_count(filter_kwargs),
            "First Request": self.format_request_for_song(await self.usage_db.get_first_request(filter_kwargs)),
            "Most Recent Request": self.format_request_for_song(await self.usage_db.get_latest_request(filter_kwargs)),
            "Total Time Played": format_time_str(await self.usage_db.get_total_play_duration(filter_kwargs)),
            "Most Frequent Requester": await self.get_most_frequent_requester_formatted(filter_kwargs)
        }
        song_stats = SongStats(yt_video, stats)
        return song_stats
    
    async def create_user_song_stats(
            self, 
            filter_kwargs: dict[str, Any], 
            user: discord.Member, 
            yt_search_query: Optional[str] = None, 
            yt_video_url: Optional[str] = None) -> UserSongStats:
        
        if yt_search_query:
            yt_video = await YoutubeVideo.from_search_query(yt_search_query)
        else:
            yt_video = await YoutubeVideo.from_url(yt_video_url)
        
        filter_kwargs["requester_id"] = user.id
        filter_kwargs["song_id"] = yt_video.video_id

        stats = {
            "Times Requested": await self.usage_db.get_song_request_count(filter_kwargs),
            "Times Played": await self.usage_db.get_song_play_count(filter_kwargs),
            "First Request": await self.usage_db.get_first_request(filter_kwargs).timestamp,
            "Most Recent Request": await self.usage_db.get_latest_request(filter_kwargs).timestamp,
            "Total Time Played": format_time_str(await self.usage_db.get_total_play_duration(filter_kwargs)),
        }
        user_song_stats = UserSongStats(user, yt_video, stats)
        return user_song_stats

    async def format_request_for_server(self, song_request: SongRequest) -> str:
        if not song_request:
            return "N/A"
        formatted_for_user = await self.format_request_for_user(song_request)
        formatted_for_song = self.format_request_for_song(song_request)
        fully_formatted = formatted_for_song + formatted_for_user[formatted_for_user.rfind(","):]
        return fully_formatted

    async def format_request_for_user(self, song_request: SongRequest) -> str:
        if not song_request:
            return "N/A"
        yt_video = await YoutubeVideo.from_id(song_request.song_id)
        return f"{format_datetime(song_request.timestamp)}, requesting {yt_video.video_link_markdown}"
    
    def format_request_for_song(self, song_request: SongRequest) -> str:
        if not song_request:
            return "N/A"
        requester = self.ctx.guild.get_member(song_request.requester_id)
        return f"{format_datetime(song_request.timestamp)}, by {requester.mention}"

    async def get_most_frequent_requester_formatted(self, filter_kwargs: dict[str, Any]) -> str:
        requester_id, request_count = await self.usage_db.get_most_frequent_requester(filter_kwargs)
        if not requester_id or not request_count:
            return "N/A"
        requester = self.ctx.guild.get_member(requester_id)
        formatted = f"{requester.mention} with {request_count} request{'s' if request_count > 1 else ''}"
        return formatted

    async def get_most_requested_song_formatted(self, filter_kwargs: dict[str, Any]) -> str:
        song_id, request_count = await self.usage_db.get_most_requested_song(filter_kwargs)
        if not song_id or not request_count:
            return "N/A"
        yt_video = await YoutubeVideo.from_id(song_id)
        formatted = f"{yt_video.video_link_markdown} with {request_count} request{'s' if request_count > 1 else ''}"
        return formatted
    