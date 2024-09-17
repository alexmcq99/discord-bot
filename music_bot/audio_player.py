"""Contains class AudioPlayer to poll the song queue and play audio in discord."""

import asyncio
import traceback
from queue import LifoQueue

from discord import Embed, VoiceClient

from config import Config

from .song import Song, SongQueue
from .usage_database import UsageDatabase


class AudioError(Exception):
    """A custom exception class to raise in case of an error with the audio player."""

    pass


class AudioPlayer:
    """Handles polling the song queue and playing audio in the discord voice client.

    Attributes:
        config: A Config object representing the configuration of the music bot.
        usage_db: A UsageDatabase object representing the database tracking usage data for the music bot.
        current_song: Song object representing the current song playing (or about to be played).
        voice_client: The discord VoiceClient object to play audio with.
        song_queue: The SongQueue object to poll songs from.
        event_loop: The asyncio event loop that the music bot runs in.
        play_next_song_event: An asyncio.Event object indicating if it's time to play the next song.
        audio_player_task: An asyncio.Task that continuously polls the song queue
            and plays audio with the discord client.
    """

    def __init__(self, config: Config, usage_db: UsageDatabase) -> None:
        """Initializes the audio player.

        Args:
            config: A Config object representing the configuration of the music bot.
            usage_db: A UsageDatabase object representing the database tracking usage data for the music bot.
        """
        self.config: Config = config
        self.usage_db: UsageDatabase = usage_db
        self.prev_songs: list[Song] = []
        self.push_to_prev_songs: bool = True
        self.current_song: Song = None
        self.voice_client: VoiceClient = None
        self.song_queue: SongQueue = SongQueue(config)
        self.event_loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
        self.play_next_song_event: asyncio.Event = asyncio.Event()
        self.audio_player_task: asyncio.Task = None

    def __del__(self) -> None:
        """Cancels the audio player task before destroying the audio player object."""
        if self.audio_player_task:
            self.audio_player_task.cancel()

    @property
    def is_currently_playing(self) -> bool:
        """Checks if the audio player is currently playing audio.

        Returns:
            True if the audio player is currently playing audio; otherwise, False.
        """
        return bool(self.voice_client and self.current_song)

    @property
    def is_queue_looping(self) -> bool:
        """Checks if the song queue is looping or not.

        Returns:
            True if the song queue is looping; otherwise, False.
        """
        return self.song_queue.is_looping

    def flip_is_queue_looping(self) -> None:
        """Flips whether or not the song queue is looping."""
        self.song_queue.flip_is_looping()

    def start_audio_player(self) -> None:
        """Starts the audio player task."""
        print("Starting the audio player.")
        self.audio_player_task = self.event_loop.create_task(self.play_audio())

    async def play_audio(self) -> None:
        """Continuously polls the song queue and plays the next song.

        In an infinite loop, poll the song queue and play the audio for the next song in the discord voice client.
        If it waits too long for a new song to play, the task will time out from inactivity.
        """
        try:
            while True:
                self.play_next_song_event.clear()

                try:
                    print("About to wait for next song.")
                    await asyncio.wait_for(
                        self.poll_song_queue(), self.config.inactivity_timeout
                    )
                except asyncio.TimeoutError:
                    await self.leave()
                    return

                print(f"about to play song: {self.current_song}")
                self.current_song.record_start()
                self.voice_client.play(
                    self.current_song.audio_source, after=self.play_next_song
                )

                print(f"Sending embed")
                await self.current_song.channel_where_requested.send(
                    embed=self.current_song.create_embed()
                )

                await self.play_next_song_event.wait()
        except Exception as e:
            print("PRINTING EXCEPTION: ", traceback.format_exc())

    async def poll_song_queue(self) -> None:
        """Waits to poll the next song from the song queue and sets the current song."""
        print("waiting to poll")
        self.current_song = await self.song_queue.get()

    def add_to_song_queue(self, song: Song, play_next: bool = False) -> None:
        """Adds a song to the song queue.

        Args:
            song: The Song object to add to the queue.
            play_next: A boolean indicating whether or not to play the song next or after all the other songs.
        """
        self.song_queue.put_nowait(song, play_next=play_next)

    def remove_from_song_queue(
        self, index: int = None, song_ids: set[str] = None
    ) -> Song:
        """Removes the song at the specified index from the song queue.

        Args:
            index: The index of the song queue to remove.
            song_ids: A set of string song ids to look for when removing a song.

        Returns:
            The Song object removed from the song queue.
        """
        return self.song_queue.remove(index=index, song_ids=song_ids)

    def clear_song_queue(self) -> None:
        """Clears the song queue."""
        self.song_queue.clear()

    def get_song_queue_embed(self, page: int = 1) -> Embed:
        """Gets the discord embed for the song queue.

        Args:
            page: Integer representing which page of the queue to get.

        Returns:
            The discord.Embed object displaying the state of the song queue.
        """
        return self.song_queue.create_embed(page)

    def shuffle_song_queue(self) -> None:
        """Randomly shuffles the song queue."""
        self.song_queue.shuffle()

    def play_next_song(self, play_audio_error: Exception = None):
        """Gets the audio player ready to play the next song.

        This function is used as the "after" callback for self.voice_client.play() in play_audio(),
        meaning that the same thread responsible for playing audio to discord will also call this function.
        Note that the "after" callback for discord's VoiceClient.play() function can only have one argument:
        the exception raised by the voice client when playing audio.

        Because this function is executed in a different thread, it needs special wrapper logic
        (such as asyncio.run_coroutine_threadsafe() with the music bot's event loop) to make sure that asynchronous
        tasks are still executed in the music bot's event loop.

        Args:
            play_audio_error: The exception raised by the discord VoiceClient while playing the previous song.
                None if there was no exception.
        """
        if play_audio_error:
            print("Error: ", play_audio_error)
            raise AudioError(str(play_audio_error))

        print("Song is done, preparing to play next song.")

        # Record song play to usage database
        asyncio.run_coroutine_threadsafe(
            self.record_song_play_to_db(self.current_song), loop=self.event_loop
        )

        if self.push_to_prev_songs:
            self.prev_songs.append(self.current_song)
        else:
            self.push_to_prev_songs = True

        self.current_song = None
        self.play_next_song_event.set()

    async def skip(self, back: bool = False) -> bool:
        """Skips the current song and starts playing the next one.

        Returns:
            True if the song was skipped successfully; False if there was no song playing.
        """
        if self.voice_client.is_playing():
            if back:
                self.song_queue.put_nowait(self.current_song, play_next=True)
                self.song_queue.put_nowait(self.prev_songs.pop(), play_next=True)
                self.push_to_prev_songs = False
            self.voice_client.stop()
            return True
        return False

    def pause(self) -> bool:
        """Pauses the current song.

        Returns:
            True if the song was paused successfully; False if there was no song playing
                or the current song was already paused.
        """
        if self.voice_client.is_playing():
            self.voice_client.pause()
            self.current_song.record_stop()
            return True
        return False

    def resume(self) -> bool:
        """Resumes the current song, assuming it's paused.

        Returns:
            True if the song was resumed successfully; False if there was no song playing
                or the current one wasn't paused.
        """
        if self.voice_client.is_paused():
            self.current_song.record_start()
            self.voice_client.resume()
            return True
        return False

    async def stop(self) -> bool:
        """Stops the audio player.

        Returns:
            True if the audio player was stopped successfully; False if there was no song playing.
        """
        if self.is_currently_playing:
            self.clear_song_queue()
            self.voice_client.stop()
            return True
        return False

    async def leave(self) -> bool:
        """Stops the audio player and makes the bot leave the current voice channel.

        Returns:
            True if the bot successfully leaves the voice channel; False if the bot
                wasn't in a voice channel to begin with.
        """
        if self.voice_client:
            await self.stop()
            await self.voice_client.disconnect()
            self.voice_client = None
            return True
        return False

    async def record_song_play_to_db(self, song: Song) -> None:
        """Records a song play in the usage database."""
        print("Entered record_song_play_to_db().")
        if self.config.enable_usage_database:
            print("Recording stats, so we can record this song play.")
            song.record_stop()
            print("Finished recording song stop.")
            song_play = song.create_song_play()
            print(f"Created song play in record_song_play_to_db(): {song_play!r}")
            await self.usage_db.insert_data(song_play)
