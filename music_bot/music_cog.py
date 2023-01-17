import asyncio
from .audio_player import AudioPlayer
from config.config import Config
import discord
from discord.ext import commands
from .downloader import Downloader
import math
from .songs import SongFactory

class MusicCog(commands.Cog):
    def __init__(self, bot: commands.Bot, config: Config):
        self.bot: commands.Bot = bot
        self.config: Config = config
        self.audio_players: dict[int, AudioPlayer] = dict()
        self.download_manager: Downloader = Downloader(bot)
        self.song_factory: SongFactory = SongFactory(config, bot)

    def get_audio_player(self, guild_id: int) -> AudioPlayer:
        audio_player = self.audio_players.get(guild_id)
        if audio_player:
            print("Retrieved audio manager")
        if not audio_player:
            audio_player = AudioPlayer(self.bot, self.config.inactivity_timeout)
            self.audio_players[guild_id] = audio_player
            print(f"Stored audio manager: {audio_player}")
        return audio_player
        
    def cog_unload(self):
        for audio_player in self.audio_players.values():
            self.bot.loop.create_task(audio_player.stop())

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
    
    @commands.command(name='join', aliases=['summon'], invoke_without_subcommand=True)
    async def join(self, ctx: commands.Context):
        """Joins a voice channel."""

        destination = ctx.author.voice.channel
        if ctx.audio_player.voice_client:
            await ctx.audio_player.voice.move_to(destination)
            return

        ctx.audio_player.voice_client = await destination.connect()

    @commands.command(name='leave', aliases=['disconnect', 'die'])
    @commands.has_permissions(manage_guild=True)
    async def leave(self, ctx: commands.Context):
        """Clears the queue and leaves the voice channel."""

        if not ctx.audio_player.voice:
            return await ctx.send('Not connected to any voice channel.')

        await ctx.audio_player.stop()
        del self.audio_players[ctx.guild.id]

    @commands.command(name='volume')
    async def volume(self, ctx: commands.Context, volume: str):
        """Sets the volume of the player."""

        if not ctx.audio_player.is_playing:
            return await ctx.send('Nothing being played at the moment.')

        if 0 > volume > 100:
            return await ctx.send('Volume must be between 0 and 100')

        ctx.audio_player.volume = volume / 100
        await ctx.send('Volume of the player set to {}%'.format(volume))

    @commands.command(name='pause')
    @commands.has_permissions(manage_guild=True)
    async def pause(self, ctx: commands.Context):
        """Pauses the currently playing song."""

        if ctx.audio_player.is_playing and ctx.audio_player.voice.is_playing():
            ctx.audio_player.voice.pause()
            await ctx.message.add_reaction('⏯')

    @commands.command(name='resume')
    @commands.has_permissions(manage_guild=True)
    async def resume(self, ctx: commands.Context):
        """Resumes a currently paused song."""

        if ctx.audio_player.is_playing and ctx.audio_player.voice.is_paused():
            ctx.audio_player.voice.resume()
            await ctx.message.add_reaction('⏯')

    @commands.command(name='stop')
    @commands.has_permissions(manage_guild=True)
    async def stop(self, ctx: commands.Context):
        """Stops playing song and clears the queue."""

        ctx.audio_player.request_queue.clear()

        if ctx.audio_player.is_playing:
            ctx.audio_player.voice.stop()
            await ctx.message.add_reaction('⏹')

    @commands.command(name='skip')
    async def skip(self, ctx: commands.Context):
        """Skip a song."""
        if not ctx.audio_player.is_playing:
            return await ctx.send('Not playing any music right now.')

        await ctx.message.add_reaction('⏭')
        ctx.audio_player.skip()

    @commands.command(name='queue')
    async def queue(self, ctx: commands.Context, *, page: int = 1):
        """Shows the player's queue.
        You can optionally specify the page to show. Each page contains 10 elements.
        """

        if ctx.audio_player.request_queue:
            return await ctx.send('Empty queue.')

        items_per_page = 10
        pages = math.ceil(len(ctx.audio_player.request_queue) / items_per_page)

        start = (page - 1) * items_per_page
        end = start + items_per_page

        queue = ''
        for i, song in enumerate(ctx.audio_player.request_queue[start:end], start=start):
            queue += '`{0}.` [**{1.source.title}**]({1.source.url})\n'.format(i + 1, song)

        embed = (discord.Embed(description='**{} tracks:**\n\n{}'.format(len(ctx.audio_player.request_queue), queue))
                 .set_footer(text='Viewing page {}/{}'.format(page, pages)))
        await ctx.send(embed=embed)

    @commands.command(name='shuffle')
    async def shuffle(self, ctx: commands.Context):
        """Shuffles the queue."""

        if not ctx.audio_player.request_queue:
            return await ctx.send('Empty queue.')

        ctx.audio_player.request_queue.shuffle()
        await ctx.message.add_reaction('✅')

    @commands.command(name='remove')
    async def remove(self, ctx: commands.Context, index: int):
        """Removes a song from the queue at a given index."""

        if not ctx.audio_player.request_queue:
            return await ctx.send('Empty queue.')

        ctx.audio_player.request_queue.remove(index - 1)
        await ctx.message.add_reaction('✅')

    @commands.command(name='loop')
    async def loop(self, ctx: commands.Context):
        """Loops the queue.
        Invoke this command again to unloop the queue.
        """

        if not ctx.audio_player.is_playing:
            return await ctx.send('Nothing being played at the moment.')

        ctx.audio_player.loop = not ctx.audio_player.loop
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

            if not ctx.audio_player.voice_client:
                await ctx.invoke(self.join)
            for request in song_requests:
                await ctx.audio_player.request_queue.put(request)
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
    
    # @commands.Cog.listener()
    # async def on_audio_player_update(member, before, after):
    # global curr_song_id, is_looping, song_queue
    # if not member.id == bot.user.id:
    #     return
    # elif before.channel is None:
    #     voice_client = after.channel.guild.voice_client
    #     time = 0
    #     while True:
    #         await asyncio.sleep(1)
    #         time += 1
    #         if not voice_client.is_connected():
    #             break
    #         elif voice_client.is_playing() and not voice_client.is_paused() and after.channel.members.size >= 1:
    #             time = 0
    #         elif time == config.inactivity_timeout:
    #             if voice_client.is_paused(): # If paused, completely stop
    #                 curr_song_id = None
    #                 is_looping = False
    #                 song_queue.clear()
    #                 voice_client.stop()
    #             logging.debug("Bot disconnected due to inactivity.")
    #             await voice_client.disconnect()
    