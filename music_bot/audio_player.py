import asyncio
import traceback
from datetime import datetime

from discord import VoiceClient
from discord.ext.commands import Bot

from config import Config

from .song import Song, SongQueue
from .usage_database import UsageDatabase


class AudioError(Exception):
    pass

class AudioPlayer:
    def __init__(self, config: Config, bot: Bot, usage_db: UsageDatabase):
        self.bot: Bot = bot
        self.usage_db: UsageDatabase = usage_db
        self.inactivity_timeout: int = config.inactivity_timeout
        self.current_song: Song = None
        self.voice_client: VoiceClient = None
        self.song_queue: SongQueue[Song] = SongQueue(config.max_shown_songs)
        self.is_looping: bool = False
        self.play_next_song_event: asyncio.Event = asyncio.Event()
        self.audio_player: asyncio.Task = None

    def __del__(self):
        if self.audio_player:
            self.audio_player.cancel()

    @property
    def is_playing(self) -> bool:
        return bool(self.voice_client and self.current_song)

    def start_audio_player(self) -> None:
        self.audio_player = self.bot.loop.create_task(self.play_audio())
    
    async def play_audio(self) -> None:
        try:
            while True:
                self.play_next_song_event.clear()

                try:
                    await asyncio.wait_for(self.poll_song_queue(), self.inactivity_timeout)
                except asyncio.TimeoutError:
                    self.bot.loop.create_task(self.stop())
                    return
                
                print(f"about to play song: {self.current_song}")
                self.current_song.timestamp_last_played = datetime.now()
                self.voice_client.play(self.current_song.audio_source, after=self.play_next_song)
                print(f"Sending embed")
                await self.current_song.channel_where_requested.send(embed=self.current_song.create_embed())

                await self.play_next_song_event.wait()
        except Exception as e:
            print("PRINTING EXCEPTION: ", traceback.format_exc())

    async def poll_song_queue(self):
        print("waiting to poll")
        self.current_song = await self.song_queue.get()

    def play_next_song(self, error=None):
        if error:
            print("Error: ", error)
            raise AudioError(str(error))

        print("Song is done, preparing to play next song.")
        asyncio.run_coroutine_threadsafe(self.record_song_play(), loop=self.bot.loop)
        if self.is_looping:
            self.song_queue.put_nowait(self.current_song)
        self.current_song = None
        self.play_next_song_event.set()

    async def skip(self):
        if self.voice_client.is_playing():
            self.voice_client.stop()
            await self.record_song_play()
            return True
        return False

    async def stop(self):
        self.song_queue.clear()
        if self.current_song:
            await self.record_song_play()
        if self.voice_client:
            await self.voice_client.disconnect()
            self.voice_client = None
    
    async def record_song_play(self):
        self.current_song.record_stop()
        await self.usage_db.insert_data(self.current_song.create_song_play())