import asyncio
import re
import traceback

from asyncspotify import SpotifyException
from discord.ext import commands
from yt_dlp.utils import YoutubeDLError

from config import Config

from .audio_player import AudioPlayer
from .song_factory import SongFactory
from .stats import StatsFactory
from .usage_database import UsageDatabase
from .ytdl_wrapper import YtdlWrapper


class MusicCog(commands.Cog):
    def __init__(self, bot: commands.Bot, config: Config):
        self.bot: commands.Bot = bot
        self.config: Config = config
        self.usage_db: UsageDatabase = UsageDatabase(config)
        self.ytdl_wrapper: YtdlWrapper = YtdlWrapper(bot)
        self.song_factory: SongFactory = SongFactory(config, self.usage_db, self.ytdl_wrapper)
        self.stats_factory: StatsFactory = StatsFactory(config, self.usage_db, self.ytdl_wrapper)
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
        print(ctx.audio_player)
        return

    async def cog_after_invoke(self, ctx):
        print("Stopping the cog")
        try:
            print(f"Exception in audio player: {ctx.audio_player.audio_player.exception()}")
        except Exception as e:
            print("Exception when printing exception: ", str(e))
        await ctx.message.add_reaction(self.reactions.get(ctx.command.name, self.default_reaction))
    
    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: Exception):
        print(type(error))
        if isinstance(error, commands.CommandNotFound):
            await ctx.send(f"Command not found. Type \"-help\" to see the list of valid commands.")
        elif isinstance(error, commands.UserInputError):
            await ctx.send(f"Bad user input received: {str(error)}")
        elif isinstance(error, YoutubeDLError):
            await ctx.send(f"YoutubeDL threw an error with the following message: {str(error)}")
        elif isinstance(error, SpotifyException):
            await ctx.send(f"Encountered an error when getting Spotify data. Please check if the given Spotify url is valid.")
        else:
            await ctx.send(f"An unexpected error occurred in {ctx.command.name}: {str(error)}")
        
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
        print(ctx.audio_player.voice_client)

    @commands.command(name='leave', aliases=['disconnect', 'die'])
    async def leave(self, ctx: commands.Context):
        """Clears the queue and leaves the voice channel."""

        print(ctx.audio_player.voice_client)
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

        await ctx.send(f"The queue is {'currently' if ctx.audio_player.is_looping else 'not'} looping.")
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
        
        possible_user_mention = args[0]
        user_mention_pattern = r"<!?@(\d+)>" # <@1293190231243>, <!@1293190231243>
        if match := re.match(user_mention_pattern, possible_user_mention):
            user_id = int(match.group(1))
            user = ctx.guild.get_member(user_id)
            if user:
                kwargs['user'] = user
                print(f"Found user mention: {possible_user_mention}")

        if len(args) > 1:
            kwargs['ytdl_args'] = ' '.join(args[1:])

        return kwargs

    @commands.command(name='stats')
    async def stats(self, ctx: commands.Context, *args):
        """Gets stats on a song, user, or server"""

        kwargs = await self.parse_stats_args(ctx, args)
        stats = await self.stats_factory.create_stats(ctx, **kwargs)
        await ctx.send(embed=stats.create_main_embed())
        if self.config.get_usage_graph_with_stats and stats.figure_filename:
            figure_file, embed = stats.create_figure_embed()
            # await ctx.send(embed=embed, file=figure_file)
            await ctx.send(file=figure_file)

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
        await ctx.send(f"The queue is {'now' if ctx.audio_player.is_looping else 'no longer'} looping.")

    async def _play(self, ctx: commands.Context, args: str, play_next : bool = False):
        print('Type of args:', type(args))
        if not args:
            raise commands.UserInputError("No arguments provided. Please provide a url or search query.")

        if not ctx.audio_player.voice_client:
            print("joining voice channel")
            await ctx.invoke(self.join)
        async with ctx.typing():
            if not ctx.audio_player.audio_player or ctx.audio_player.audio_player.done():
                ctx.audio_player.start_audio_player()
            async for song in self.song_factory.create_songs(ctx, args):
                if play_next:
                    await ctx.audio_player.song_queue.put_left(song)
                    await ctx.send(f"Playing {song} next.")
                else:
                    await ctx.audio_player.song_queue.put(song)
                    await ctx.send(f"Enqueued {song}.")
                    
    @commands.command(name='play')
    async def play(self, ctx: commands.Context, *, args: str):
        """Plays a song.
        If there are other songs in the queue, this song will be added after them.
        """
        await self._play(ctx, args)

    @commands.command(name='playnext')
    async def playnext(self, ctx: commands.Context, *, args: str):
        """Plays a song next.
        If there are other songs in the queue, this song will take priority and will be played before them.
        """
        await self._play(ctx, args, play_next = True)

    @join.before_invoke
    @play.before_invoke
    async def ensure_voice_connection(self, ctx: commands.Context):
        if not ctx.author.voice or not ctx.author.voice.channel:
            raise commands.CommandError('You are not connected to any voice channel.')

        if ctx.voice_client:
            if ctx.voice_client.channel != ctx.author.voice.channel:
                raise commands.CommandError('Bot is already in a voice channel.')