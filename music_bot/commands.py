import asyncio
from config.config import Config
import discord
from discord.ext import commands
import math
from songs import Song, SongRequest, SongRequestQueue
from song_factory import SongFactory
import spotify
import validators
import youtube

class AudioError(Exception):
    pass

class AudioManager:
    def __init__(self, bot: commands.Bot, inactivity_timeout: int):
        self.bot: commands.Bot = bot
        self.inactivity_timeout: int = inactivity_timeout
        self.current_song: SongRequest = None
        self.voice_client: discord.VoiceProtocol = None
        self.request_queue: SongRequestQueue[SongRequest] = SongRequestQueue()
        self.is_looping: bool = False
        self.volume: float = 0.5
        self.play_next_song_event: asyncio.Event = asyncio.Event()
        self.ctx: commands.Context = None
        self.audio_player: asyncio.Task = bot.loop.create_task(self.audio_player_task())

    def __del__(self):
        self.audio_player.cancel()

    @property
    def is_playing(self):
        return self.voice_client and self.current_song

    async def audio_player_task(self):
        while True:
            self.play_next_song_event.clear()

            try:
                async with asyncio.timeout(self.inactivity_timeout):
                    self.current_song = await self.request_queue.get()
            except asyncio.TimeoutError:
                self.bot.loop.create_task(self.stop())
                return

            if not self.current_song.downloaded:
                await self.ctx.send(f"Downloading {self.current_song.title}, please wait.")
                await self.current_song.download_event.wait()
            
            self.current_song.audio_source.volume = self.volume
            self.voice_client.play(self.current_song.audio_source, after=self.play_next_song)
            await self.ctx.send(embed=self.current.create_embed())

            await self.play_next_song_event.wait()

    def play_next_song(self, error=None):
        if error:
            raise AudioError(str(error))

        if self.is_looping:
            self.request_queue.put(self.current_song)
        self.current_song = None
        self.play_next_song_event.set()

    def skip(self):
        if self.is_playing:
            self.voice_client.stop()

    async def stop(self):
        self.request_queue.clear()

        if self.voice_client:
            await self.voice_client.disconnect()
            self.voice_client = None

class DownloadManager:
    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot
        self.current_song: Song = None
        self.download_queue: asyncio.Queue[Song] = asyncio.Queue()
        self.downloader: asyncio.Task = bot.loop.create_task(self.downloader_task())
        self.current_download_task: asyncio.Task = None

    def __del__(self):
        self.downloader.cancel()

    @property
    def is_downloading(self):
        return self.current_download is not None

    async def downloader_task(self):
        while True:
            self.current_song = await self.download_queue.get()
            download_task = self.bot.loop.create_task(self.current_song.download())


class VoiceError(Exception):
    pass

class MusicCog(commands.Cog):
    def __init__(self, bot: commands.Bot, config: Config):
        self.bot: commands.Bot = bot
        self.config: Config = config
        self.audio_managers: dict[int, AudioManager] = dict()
        self.download_manager: DownloadManager = DownloadManager(bot)
        self.song_factory: SongFactory = SongFactory(config, bot)

    def cog_unload(self):
        for audio_manager in self.audio_managers.values():
            self.bot.loop.create_task(audio_manager.stop())

    def cog_check(self, ctx: commands.Context):
        if not ctx.guild:
            raise commands.NoPrivateMessage('This command can\'t be used in DM channels.')

        return True

    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        await ctx.send('An error occurred: {}'.format(str(error)))

    def get_audio_manager(self, ctx: commands.Context) -> AudioManager:
        audio_manager = self.audio_managers.get(ctx)
        if not audio_manager:
            audio_manager = AudioManager(self.bot)
            self.audio_managers[ctx.guild.id] = audio_manager
        audio_manager.ctx = ctx
        return audio_manager

    @commands.command(name='join', aliases=['summon'], invoke_without_subcommand=True)
    async def join(self, ctx: commands.Context):
        """Joins a voice channel."""

        destination = ctx.author.voice.channel
        audio_manager = self.get_audio_manager(ctx)
        if audio_manager.voice_client:
            await audio_manager.voice.move_to(destination)
            return

        audio_manager.voice_client = await destination.connect()

    @commands.command(name='leave', aliases=['disconnect', 'die'])
    @commands.has_permissions(manage_guild=True)
    async def leave(self, ctx: commands.Context):
        """Clears the queue and leaves the voice channel."""

        audio_manager = self.get_audio_manager(ctx)
        if not audio_manager.voice:
            return await ctx.send('Not connected to any voice channel.')

        await audio_manager.stop()
        del self.audio_managers[ctx.guild.id]

    @commands.command(name='volume')
    async def volume(self, ctx: commands.Context, volume: str):
        """Sets the volume of the player."""

        audio_manager = self.get_audio_manager(ctx)
        if not audio_manager.is_playing:
            return await ctx.send('Nothing being played at the moment.')

        if 0 > volume > 100:
            return await ctx.send('Volume must be between 0 and 100')

        audio_manager.volume = volume / 100
        await ctx.send('Volume of the player set to {}%'.format(volume))

    @commands.command(name='pause')
    @commands.has_permissions(manage_guild=True)
    async def pause(self, ctx: commands.Context):
        """Pauses the currently playing song."""

        audio_manager = self.get_audio_manager(ctx)
        if not audio_manager.is_playing and audio_manager.voice.is_playing():
            audio_manager.voice.pause()
            await ctx.message.add_reaction('⏯')

    @commands.command(name='resume')
    @commands.has_permissions(manage_guild=True)
    async def resume(self, ctx: commands.Context):
        """Resumes a currently paused song."""

        audio_manager = self.get_audio_manager(ctx)
        if not audio_manager.is_playing and audio_manager.voice.is_paused():
            audio_manager.voice.resume()
            await ctx.message.add_reaction('⏯')

    @commands.command(name='stop')
    @commands.has_permissions(manage_guild=True)
    async def stop(self, ctx: commands.Context):
        """Stops playing song and clears the queue."""

        audio_manager = self.get_audio_manager(ctx)
        audio_manager.request_queue.clear()

        if not audio_manager.is_playing:
            audio_manager.voice.stop()
            await ctx.message.add_reaction('⏹')

    @commands.command(name='skip')
    async def skip(self, ctx: commands.Context):
        """Skip a song."""

        audio_manager = self.get_audio_manager(ctx)
        if not audio_manager.is_playing:
            return await ctx.send('Not playing any music right now.')

        await ctx.message.add_reaction('⏭')
        audio_manager.skip()

    @commands.command(name='queue')
    async def queue(self, ctx: commands.Context, *, page: int = 1):
        """Shows the player's queue.
        You can optionally specify the page to show. Each page contains 10 elements.
        """

        audio_manager = self.get_audio_manager(ctx)
        if len(audio_manager.request_queue) == 0:
            return await ctx.send('Empty queue.')

        items_per_page = 10
        pages = math.ceil(len(audio_manager.request_queue) / items_per_page)

        start = (page - 1) * items_per_page
        end = start + items_per_page

        queue = ''
        for i, song in enumerate(audio_manager.request_queue[start:end], start=start):
            queue += '`{0}.` [**{1.source.title}**]({1.source.url})\n'.format(i + 1, song)

        embed = (discord.Embed(description='**{} tracks:**\n\n{}'.format(len(audio_manager.request_queue), queue))
                 .set_footer(text='Viewing page {}/{}'.format(page, pages)))
        await ctx.send(embed=embed)

    @commands.command(name='shuffle')
    async def shuffle(self, ctx: commands.Context):
        """Shuffles the queue."""

        audio_manager = self.get_audio_manager(ctx)
        if len(audio_manager.request_queue) == 0:
            return await ctx.send('Empty queue.')

        audio_manager.request_queue.shuffle()
        await ctx.message.add_reaction('✅')

    @commands.command(name='remove')
    async def remove(self, ctx: commands.Context, index: int):
        """Removes a song from the queue at a given index."""

        audio_manager = self.get_audio_manager(ctx)
        if len(audio_manager.request_queue) == 0:
            return await ctx.send('Empty queue.')

        audio_manager.request_queue.remove(index - 1)
        await ctx.message.add_reaction('✅')

    @commands.command(name='loop')
    async def loop(self, ctx: commands.Context):
        """Loops the queue.
        Invoke this command again to unloop the queue.
        """

        audio_manager = self.get_audio_manager(ctx)
        if not audio_manager.is_playing:
            return await ctx.send('Nothing being played at the moment.')

        audio_manager.loop = not audio_manager.loop
        await ctx.message.add_reaction('✅')
        
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
            song_requests = self.song_factory.create_song_requests(args)

            audio_manager = self.get_audio_manager(ctx.guild.id)
            if not audio_manager.voice_client:
                await ctx.invoke(self.join)
            for request in song_requests:
                await audio_manager.request_queue.put(request)
                await self.dow
                await ctx.send(f"Enqueued {request}.")

    @join.before_invoke
    @play.before_invoke
    async def ensure_voice_connection(self, ctx: commands.Context):
        if not ctx.author.voice or not ctx.author.voice.channel:
            raise commands.CommandError('You are not connected to any voice channel.')

        if ctx.voice_client:
            if ctx.voice_client.channel != ctx.author.voice.channel:
                raise commands.CommandError('Bot is already in a voice channel.')
    
    @commands.Cog.listener()
    async def on_audio_manager_update(member, before, after):
    global curr_song_id, is_looping, song_queue
    if not member.id == bot.user.id:
        return
    elif before.channel is None:
        voice_client = after.channel.guild.voice_client
        time = 0
        while True:
            await asyncio.sleep(1)
            time += 1
            if not voice_client.is_connected():
                break
            elif voice_client.is_playing() and not voice_client.is_paused() and after.channel.members.size >= 1:
                time = 0
            elif time == config.inactivity_timeout:
                if voice_client.is_paused(): # If paused, completely stop
                    curr_song_id = None
                    is_looping = False
                    song_queue.clear()
                    voice_client.stop()
                logging.debug("Bot disconnected due to inactivity.")
                await voice_client.disconnect()
    