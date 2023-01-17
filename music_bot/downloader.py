import asyncio
from concurrent.futures import ThreadPoolExecutor
from discord.ext.commands import Bot
from .songs import Song

class Downloader:
    def __init__(self, bot: Bot):
        self.bot: Bot = bot
        self.current_song: Song = None
        self.download_queue: asyncio.Queue[Song] = asyncio.Queue()
        self.download_poller: asyncio.Task = bot.loop.create_task(self.downloader_task())
        self.downloader: asyncio.Task = None

    def __del__(self):
        self.download_poller.cancel()

    @property
    def is_downloading(self):
        return self.current_download is not None

    async def poll_downloads(self):
        while True:
            self.download_next_song_event.clear()

            print("Getting next song to download")
            self.current_song = await self.download_queue.get()
            if self.current_song.is_queued:
                print("Song is queued")
                self.downloader = self.bot.loop.create_task(self.current_song.download(after=self.download_next_song))
                self.listener = self.bot.loop.create_task(self.removed_from_queues_listener())

            print("Waiting for download to finish")
            await self.current_song.download_event.wait()
    
    def download_next_song(self, *_):
        print("Done downloading, preparing to download next song.")
        self.current_song.download_event.set()
    
    async def removed_from_queues_listener(self):
        await self.current_song.removed_from_queues_event.wait()
        self.download.cancel()
