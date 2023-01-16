import asyncio
from config.config import Config
import discord
from discord.ext import commands
import math
import os
from pytube.exceptions import PytubeError
from .songs import Song, SongQueue
from .song_factory import SongFactory
import traceback

class AudioError(Exception):
    pass

class AudioManager:
    def __init__(self, bot: commands.Bot, inactivity_timeout: int):
        self.bot: commands.Bot = bot
        self.inactivity_timeout: int = inactivity_timeout

        self.current_song: Song = None
        self.voice_client: discord.VoiceClient = None
        self.song_queue: SongQueue[Song] = SongQueue()
        self.is_looping: bool = False
        self.volume: float = 0.5
        self.play_next_song_event: asyncio.Event = asyncio.Event()

        print("about to make audio manager")
        self.audio_player: asyncio.Task = bot.loop.create_task(self.audio_player_task())

    def __del__(self) -> None:
        print("Deleting audio manager")
        self.audio_player.cancel()

    def __str__(self) -> str:
        return str(self.__dict__)

    @property
    def is_playing(self):
        return self.voice_client and self.current_song

    async def audio_player_task(self):
        while True:
            print("start of the loop")
            self.play_next_song_event.clear()

            print("About to poll")
            try:
                print("in try")
                await asyncio.wait_for(self.poll_song_queue(), self.inactivity_timeout)
            except asyncio.TimeoutError:
                print("timed out")
                self.bot.loop.create_task(self.stop())
                return
            try:
                print(f"Got song: {self.current_song}, playing now")
                # self.current_song.audio_source.volume = self.volume
                self.voice_client.play(self.current_song.audio_source, after=self.play_next_song)
                print(f"Sending embed")
                await self.current_song.channel_where_requested.send(embed=self.current_song.create_embed())
            except Exception:
                print("PRINTING EXCEPTION: ", traceback.format_exc())

            print(f"Waiting for song to finish")
            await self.play_next_song_event.wait()

    async def poll_song_queue(self):
        print("waiting to poll")
        self.current_song = await self.song_queue.get()

    def play_next_song(self, error=None):
        if error:
            print("Here is the error: ", error)
            raise AudioError(str(error))

        print("song finished, setting event to play the next song")
        if self.is_looping:
            self.song_queue.put(self.current_song)
        self.current_song = None
        self.play_next_song_event.set()

    def skip(self):
        if self.is_playing:
            self.voice_client.stop()

    async def stop(self):
        self.song_queue.clear()

        if self.voice_client:
            await self.voice_client.disconnect()
            self.voice_client = None

class MusicCog(commands.Cog):
    def __init__(self, bot: commands.Bot, config: Config):
        self.bot: commands.Bot = bot
        self.config: Config = config
        self.audio_managers: dict[int, AudioManager] = dict()
        print("init")
        self.song_factory: SongFactory = SongFactory(config, bot)

    def get_audio_manager(self, guild_id: int) -> AudioManager:
        audio_manager = self.audio_managers.get(guild_id)
        if audio_manager:
            print("Retrieved audio manager")
        if not audio_manager:
            audio_manager = AudioManager(self.bot, self.config.inactivity_timeout)
            self.audio_managers[guild_id] = audio_manager
            print(f"Stored audio manager: {audio_manager}")
        return audio_manager
        
    def cog_unload(self):
        for audio_manager in self.audio_managers.values():
            self.bot.loop.create_task(audio_manager.stop())

    def cog_check(self, ctx: commands.Context):
        if not ctx.guild:
            raise commands.NoPrivateMessage('This command can\'t be used in DM channels.')

        return True

    async def cog_before_invoke(self, ctx):
        print("Starting the cog")
        ctx.audio_manager = self.get_audio_manager(ctx.guild.id)
        return

    async def cog_after_invoke(self, ctx):
        print("Stopping the cog")
        try:
            print(f"Exception in audio player: {ctx.audio_manager.audio_player.exception()}")
        except Exception as e:
            print("Exception when printing exception: ", str(e))

    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, discord.ext.commands.errors.CommandNotFound):
            await ctx.send("Command not found. Try \"-help\" to get a list of available commands.")
        
        await ctx.send('An error occurred: {}'.format(str(error)))

    @commands.command(name='leave', aliases=['disconnect', 'die'])
    @commands.has_permissions()
    async def leave(self, ctx: commands.Context):
        """Clears the queue and leaves the voice channel."""

        if not ctx.audio_manager.voice_client:
            return await ctx.send('Not connected to any voice channel.')

        await ctx.audio_manager.stop()
        del self.audio_managers[ctx.guild.id]

    @commands.command(name='volume')
    async def volume(self, ctx: commands.Context, *, volume: int):
        """Sets the volume of the player."""

        if not ctx.audio_manager.is_playing:
            return await ctx.send('Nothing being played at the moment.')

        if volume < 0 or volume > 100:
            raise commands.CommandError('Volume must be between 0 and 100, inclusive.')

        ctx.audio_manager.volume = volume / 100
        await ctx.send(f'Volume of the player set to {volume}')

    @commands.command(name='pause')
    @commands.has_permissions(manage_guild=True)
    async def pause(self, ctx: commands.Context):
        """Pauses the currently playing song."""

        if ctx.audio_manager.is_playing and ctx.audio_manager.voice_client.is_playing():
            ctx.audio_managervoice_client.pause()
            await ctx.message.add_reaction('⏯')

    @commands.command(name='resume')
    @commands.has_permissions(manage_guild=True)
    async def resume(self, ctx: commands.Context):
        """Resumes a currently paused song."""

        if ctx.audio_manager.is_playing and ctx.audio_manager.voice_client.is_paused():
            ctx.audio_manager.voice_client.resume()
            await ctx.message.add_reaction('⏯')

    @commands.command(name='stop')
    @commands.has_permissions(manage_guild=True)
    async def stop(self, ctx: commands.Context):
        """Stops playing song and clears the queue."""

        ctx.audio_manager.song_queue.clear()

        if ctx.audio_manager.is_playing:
            ctx.audio_manager.voice_client.stop()
            await ctx.message.add_reaction('⏹')

    @commands.command(name='skip')
    async def skip(self, ctx: commands.Context):
        """Skip a song."""

        if not ctx.audio_manager.is_playing:
            return await ctx.send('Not playing any music right now.')

        await ctx.message.add_reaction('⏭')
        ctx.audio_manager.skip()

    @commands.command(name='queue')
    async def queue(self, ctx: commands.Context, *, page: int = 1):
        """Shows the player's queue.
        You can optionally specify the page to show. Each page contains 10 elements.
        """

        if not ctx.audio_manager.song_queue:
            return await ctx.send('Empty queue.')

        items_per_page = 10
        pages = math.ceil(len(ctx.audio_manager.song_queue) / items_per_page)

        start = (page - 1) * items_per_page
        end = start + items_per_page

        queue = ''
        for i, song in enumerate(ctx.audio_manager.song_queue[start:end], start=start):
            queue += '`{0}.` [**{1.title}**]({1.url})\n'.format(i + 1, song)

        embed = (discord.Embed(description='**{} tracks:**\n\n{}'.format(len(ctx.audio_manager.song_queue), queue))
                 .set_footer(text='Viewing page {}/{}'.format(page, pages)))
        await ctx.send(embed=embed)

    @commands.command(name='shuffle')
    async def shuffle(self, ctx: commands.Context):
        """Shuffles the queue."""

        if not ctx.audio_manager.song_queue:
            return await ctx.send('Empty queue.')

        ctx.audio_manager.song_queue.shuffle()
        await ctx.message.add_reaction('✅')

    @commands.command(name='remove')
    async def remove(self, ctx: commands.Context, index: int):
        """Removes a song from the queue at a given index."""

        if ctx.audio_manager.song_queue:
            return await ctx.send('Empty queue.')

        ctx.audio_manager.song_queue.remove(index - 1)
        await ctx.message.add_reaction('✅')

    @commands.command(name='loop')
    async def loop(self, ctx: commands.Context):
        """Loops the queue.
        Invoke this command again to unloop the queue.
        """

        if not ctx.audio_manager.is_playing:
            return await ctx.send('Nothing being played at the moment.')

        ctx.audio_manager.loop = not ctx.audio_manager.loop
        await ctx.message.add_reaction('✅')
    
    @commands.command(name='join', aliases=['summon'], invoke_without_subcommand=True)
    async def join(self, ctx: commands.Context):
        """Joins a voice channel."""

        destination = ctx.author.voice.channel
        if ctx.audio_manager.voice_client:
            await ctx.audio_manager.voice.move_to(destination)
            return

        ctx.audio_manager.voice_client = await destination.connect()

    @commands.command(name='play')
    async def play(self, ctx: commands.Context, *args):
        """Plays a song.
        If there are songs in the queue, this will be queued until the
        other songs finished playing.
        """

        if not args:
            raise commands.CommandError("No arguments provided. Please provide a url or search query.")

        async with ctx.typing():
            self.song_factory.ctx = ctx
            songs = self.song_factory.create_songs(args)

            if not ctx.audio_manager.voice_client:
                await ctx.invoke(self.join)
            for song in songs:
                if song:
                    try:
                        song.check_availability()
                    except PytubeError as e:
                        raise commands.CommandError(str(e))
                    await ctx.audio_manager.song_queue.put(song)
                    await ctx.send(f"Enqueued {song}.")
                    # print(len(ctx.audio_manager.song_queue))
                    # print(ctx.audio_manager.song_queue)

    @join.before_invoke
    @play.before_invoke
    async def ensure_voice_connection(self, ctx: commands.Context):
        if not ctx.author.voice or not ctx.author.voice.channel:
            raise commands.CommandError(f'{ctx.author.mention} is not connected to any voice channel.')

        if ctx.voice_client and ctx.voice_client.channel != ctx.author.voice.channel:
            raise commands.CommandError('Seraqueen is already in a voice channel.')
    
    # @commands.Cog.listener()
    # async def on_voice_state_update(self, member, before, after):
    #     if not member.id == self.bot.user.id:
    #         return
    #     elif before.channel is None:
    #         voice_client = after.channel.guild.voice_client
    #         time = 0
    #         while True:
    #             await asyncio.sleep(1)
    #             time += 1
    #             if not voice_client.is_connected():
    #                 break
    #             elif voice_client.is_playing() and not voice_client.is_paused() and after.channel.members.size >= 1:
    #                 time = 0
    #             elif time == config.inactivity_timeout:
    #                 if voice_client.is_paused(): # If paused, completely stop
    #                     curr_song_id = None
    #                     is_looping = False
    #                     song_queue.clear()
    #                     voice_client.stop()
    #                 logging.debug("Bot disconnected due to inactivity.")
    #                 await voice_client.disconnect()
    