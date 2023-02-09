import asyncio
import re
import traceback

import discord
import validators
from discord.ext import commands

from config import Config

from .audio_player import AudioPlayer
from .song_factory import SongFactory
from .spotify import is_spotify_url
from .stats import StatsFactory
from .usage_database import UsageDatabase
from .youtube import is_yt_playlist, is_yt_video


class MusicCog(commands.Cog):
    def __init__(self, bot: commands.Bot, config: Config):
        self.bot: commands.Bot = bot
        self.config: Config = config
        self.usage_db: UsageDatabase = UsageDatabase(config)
        self.song_factory: SongFactory = SongFactory(config, self.usage_db)
        self.stats_factory: StatsFactory = StatsFactory(self.usage_db)
        self.audio_players: dict[int, AudioPlayer] = dict()
        self.default_reaction: str = "✅"
        self.reactions: dict[str, str] = {
            "join": "👋",
            "leave": "👋",
            "pause": "⏯",
            "resume": "⏯",
            "stop": "⏹",
            "skip": "⏭",
            "play": "🎵",
            "loop": "🔁",
            "now": "✅",
            "queue": "✅",
            "shuffle": "🔀",
            "remove": "❌"
        }

    def get_audio_player(self, guild_id: int) -> AudioPlayer:
        print(type(self.audio_players))
        audio_player = self.audio_players.get(guild_id)
        if audio_player:
            print("Retrieved audio manager")
        if not audio_player:
            audio_player = AudioPlayer(self.config, self.bot, self.usage_db)
            self.audio_players[guild_id] = audio_player
            print(f"Stored audio manager: {audio_player}")
        return audio_player
    
    async def cog_load(self):
        await self.usage_db.initialize()
        print("booting up")

    async def cog_unload(self):
        tasks = [audio_player.stop() for audio_player in self.audio_players.values()]
        await asyncio.gather(*tasks)

    def cog_check(self, ctx: commands.Context):
        if not ctx.guild:
            raise commands.NoPrivateMessage('This command can\'t be used in DM channels.')
        return True

    async def cog_before_invoke(self, ctx):
        print("Starting the cog")
        ctx.audio_player = self.get_audio_player(ctx.guild.id)
        return

    async def cog_after_invoke(self, ctx):
        print("Stopping the cog")
        try:
            print(f"Exception in audio player: {ctx.audio_player.audio_player.exception()}")
        except Exception as e:
            print("Exception when printing exception: ", str(e))
        await ctx.message.add_reaction(self.reactions.get(ctx.command.name, self.default_reaction))
    
    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.CommandNotFound):
            await ctx.send(f"Command not found. Type \"-help\" to see the list of valid commands.")
        elif isinstance(error, commands.UserInputError):
            await ctx.send(f"Bad user input received: {str(error)}")
        else:
            await ctx.send(f"An error occurred in {ctx.command.name}: {str(error)}")
        traceback.print_exception(error)
    
    @commands.command(name='clear')
    async def clear(self, ctx: commands.Context):
        """Clears the song queue."""

        if not ctx.audio_player.song_queue:
            await ctx.send("The queue is already empty.")
        else:
            ctx.audio_player.song_queue.clear()
            await ctx.send("Cleared the queue.")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if after.channel is None:
            audio_player = self.get_audio_player(before.channel.guild.id)
            if len(before.channel.voice_states) <= 1:
                await audio_player.stop()
    
    @commands.command(name='join', aliases=['summon'], invoke_without_subcommand=True)
    async def join(self, ctx: commands.Context):
        """Joins a voice channel."""

        destination = ctx.author.voice.channel
        if ctx.audio_player.voice_client:
            await ctx.audio_player.voice_client.move_to(destination)
            return

        ctx.audio_player.voice_client = await destination.connect()

    @commands.command(name='leave', aliases=['disconnect', 'die'])
    async def leave(self, ctx: commands.Context):
        """Clears the queue and leaves the voice channel."""

        if not ctx.audio_player.voice_client:
            return await ctx.send('Not connected to any voice channel.')

        await ctx.audio_player.stop()
        del self.audio_players[ctx.guild.id]
        
    @commands.command(name='pause')
    async def pause(self, ctx: commands.Context):
        """Pauses the currently playing song."""

        if not ctx.audio_player.is_playing:
            return await ctx.send('There\'s no music to pause.')
        elif ctx.audio_player.voice_client.is_playing():
            ctx.audio_player.voice_client.pause()
            ctx.audio_player.current_song.record_stop()

    @commands.command(name='resume', aliases=['unpause', 'continue'])
    async def resume(self, ctx: commands.Context):
        """Resumes a currently paused song."""

        if not ctx.audio_player.is_playing:
            return await ctx.send('There\'s no music to resume.')
        elif ctx.audio_player.voice_client.is_paused():
            ctx.audio_player.voice_client.resume()

    @commands.command(name='stop')
    async def stop(self, ctx: commands.Context):
        """Stops playing song and clears the queue."""

        ctx.audio_player.song_queue.clear()

        if ctx.audio_player.is_playing:
            ctx.audio_player.voice_client.stop()
            self.current_song.record_stop()

    @commands.command(name='skip')
    async def skip(self, ctx: commands.Context):
        """Skip a song."""
        
        skipped = await ctx.audio_player.skip()
        if not skipped:
            return await ctx.send('Not playing any music right now.')  

    @commands.command(name='status')
    async def status(self, ctx: commands.Context):
        """Shows the current song and queue, if any.
        """

        await ctx.invoke(self.now)
        await ctx.invoke(self.queue)

    @commands.command(name='now', aliases=['current', 'playing'])
    async def now(self, ctx: commands.Context):
        """Shows the current song, if any.
        """

        if not ctx.audio_player.is_playing:
            return await ctx.send('Not playing any music right now.')
        
        await ctx.send(embed=ctx.audio_player.current_song.create_embed())

    @commands.command(name='queue')
    async def queue(self, ctx: commands.Context, *, page: int = 1):
        """Shows the player's queue.
        You can optionally specify the page to show. Each page contains 10 elements.
        """

        if not ctx.audio_player.song_queue:
            return await ctx.send('Empty queue.')

        await ctx.send(embed=ctx.audio_player.song_queue.create_embed(page))

    @commands.command(name='shuffle')
    async def shuffle(self, ctx: commands.Context):
        """Shuffles the queue."""

        if not ctx.audio_player.song_queue:
            return await ctx.send('Empty queue.')

        ctx.audio_player.song_queue.shuffle()

    async def parse_stats_args(self, ctx: commands.Context, args: tuple[str]):
        kwargs = dict()
        if not args:
            return kwargs
        
        index = 0
        possible_user_mention = args[index]
        # await ctx.send(possible_user_mention)
        pattern = r"<|!|@|>" # <@1293190231243>
        user_id_str = re.sub(pattern, "", possible_user_mention)
        if user_id_str.isdigit():
            user_id = int(user_id_str)
            user = ctx.guild.get_member(user_id)
            if user:
                kwargs["user"] = user
                index += 1
                print(f"Found user mention: {possible_user_mention}")
                if index == len(args):
                    return kwargs

        possible_url = args[index]
        if is_yt_video(possible_url):
            kwargs["yt_video_url"] = possible_url
            print("Found Youtube url: ", possible_url)
            if index + 1 < len(args):
                print(f"Ignoring arguments: {args[index + 1:]}")
        elif validators.url(possible_url):
            raise commands.BadArgument(f"Argument {possible_url} is structured like a url but is not a valid YouTube url.")
        else:
            kwargs["yt_search_query"] = " ".join(args[index:])
            print(f"Found Youtube search query: {kwargs['yt_search_query']}")
        return kwargs

    @commands.command(name='stats')
    async def stats(self, ctx: commands.Context, *args):
        """Gets stats on a song, user, or server"""

        kwargs = await self.parse_stats_args(ctx, args)
        stats = await self.stats_factory.create_stats(ctx, **kwargs)
        await ctx.send(embed=stats.create_embed())

    @commands.command(name='remove')
    async def remove(self, ctx: commands.Context, index: int):
        """Removes a song from the queue at a given index."""

        if not ctx.audio_player.song_queue:
            return await ctx.send('Empty queue.')

        ctx.audio_player.song_queue.remove(index - 1)

    @commands.command(name='loop')
    async def loop(self, ctx: commands.Context):
        """Loops the queue.
        Invoke this command again to unloop the queue.
        """

        if not ctx.audio_player.is_playing:
            return await ctx.send('Nothing being played at the moment.')

        ctx.audio_player.is_looping = not ctx.audio_player.is_looping
    
    async def parse_play_args(self, ctx: commands.Context, args: tuple[str]):
        if not args:
            raise commands.UserInputError("No arguments provided. Please provide a url or search query.")
        
        kwargs = {
            "yt_video_urls": [],
            "yt_playlist_urls": [],
            "spotify_urls": [],
        }
        found_url = False
        for possible_url in args:
            is_url = validators.url(possible_url)
            found_url = found_url or is_url
            if is_yt_video(possible_url):
                kwargs["yt_video_urls"].append(possible_url)
            elif is_yt_playlist(possible_url):
                kwargs["yt_playlist_urls"].append(possible_url)
            elif is_spotify_url(possible_url):
                kwargs["spotify_urls"].append(possible_url)
            elif validators.url(possible_url):
                await ctx.send(f"Argument {possible_url} is structured like a url but is not a valid YouTube or Spotify url.")
        if not found_url:
            kwargs["yt_search_query"] = " ".join(args)
        return kwargs

    @commands.command(name='play')
    async def play(self, ctx: commands.Context, *args):
        """Plays a song.
        If there are songs in the queue, this will be queued until the
        other songs finished playing.
        """

        kwargs = await self.parse_play_args(ctx, args)
        async with ctx.typing():
            print("getting songs")
            songs = await self.song_factory.create_songs(ctx, **kwargs)
            print("created songs")
            if not ctx.audio_player.voice_client:
                print("joining voice channel")
                await ctx.invoke(self.join)
            if not ctx.audio_player.audio_player or ctx.audio_player.audio_player.done():
                ctx.audio_player.start_audio_player()
            for song in songs:
                await ctx.audio_player.song_queue.put(song)
                await ctx.send(f"Enqueued {song}.")

    @join.before_invoke
    @play.before_invoke
    async def ensure_voice_connection(self, ctx: commands.Context):
        if not ctx.author.voice or not ctx.author.voice.channel:
            raise commands.CommandError('You are not connected to any voice channel.')

        if ctx.voice_client:
            if ctx.voice_client.channel != ctx.author.voice.channel:
                raise commands.CommandError('Bot is already in a voice channel.')