import asyncio
from discord import VoiceClient
from discord.ext.commands import Bot
from .songs import SongRequest, SongRequestQueue

class AudioError(Exception):
    pass

class AudioPlayer:
    def __init__(self, bot: Bot, inactivity_timeout: int):
        self.bot: Bot = bot
        self.inactivity_timeout: int = inactivity_timeout
        self.current_song: SongRequest = None
        self.voice_client: VoiceClient = None
        self.request_queue: SongRequestQueue[SongRequest] = SongRequestQueue()
        self.is_looping: bool = False
        self.volume: float = 0.5
        self.play_next_song_event: asyncio.Event = asyncio.Event()
        self.audio_player: asyncio.Task = bot.loop.create_task(self.play_audio())

    def __del__(self):
        self.audio_player.cancel()

    @property
    def is_playing(self) -> bool:
        return self.voice_client and self.current_song

    async def play_audio(self) -> None:
        while True:
            self.play_next_song_event.clear()

            try:
                await asyncio.wait_for(self.poll_song_queue(), self.inactivity_timeout)
            except asyncio.TimeoutError:
                self.bot.loop.create_task(self.stop())
                return

            if not self.current_song.downloaded:
                await self.ctx.send(f"Downloading {self.current_song.title}, please wait.")
                await self.current_song.download_event.wait()
            
            self.current_song.audio_source.volume = self.volume
            self.voice_client.play(self.current_song.audio_source, after=self.play_next_song)
            print(f"Sending embed")
            await self.current_song.channel_where_requested.send(embed=self.current_song.create_embed())

            await self.play_next_song_event.wait()

    async def poll_song_queue(self):
        print("waiting to poll")
        self.current_song = await self.song_queue.get()

    def play_next_song(self, error=None):
        if error:
            print("Error: ", error)
            raise AudioError(str(error))

        print("Song is done, preparing to play next song.")
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