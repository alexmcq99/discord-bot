import aiosqlite
from config.config import Config
from datetime import datetime

from typing import Optional

class MusicDatabase():
    TABLE_NAMES = ["song_requests", "song_plays"]
    DROP_TABLE_SQL = "drop table if exists {0};"
    CREATE_SONG_REQUESTS_SQL = """create table if not exists song_requests(
        timestamp text not null,
        guild_id int not null,
        requester_id int not null,
        song_id text not null,
        foreign key(song_id) references songs(id));"""
    CREATE_SONG_PLAYS_SQL = """create table if not exists song_plays(
        timestamp text not null,
        guild_id int not null,
        requester_id int not null,
        song_id text not null,
        duration int not null,
        foreign key(song_id) references songs(id));"""
    INSERT_SONG_REQUEST_SQL = """insert into song_requests(
        timestamp, guild_id, requester_id, song_id)
        values(?, ?, ?, ?)
    """
    INSERT_SONG_PLAY_SQL = """insert into song_plays(
        timestamp, guild_id, requester_id, song_id, duration)
        values(?, ?, ?, ?, ?)
    """
    SELECT_FROM_TABLE_BASE_SQL = "select * from {0}"
    GUILD_ID_WHERE_CLAUSE = "where guild_id = {0}"
    REQUESTER_ID_WHERE_CLAUSE = "where requester_id = {0}"
    SONG_ID_WHERE_CLAUSE = "where song_id = \"{0}\""
    
    def __init__(self, config: Config):
        self.database_file_path: str = config.database_file_path
        self.reset_database: bool = config.reset_database
        self.drop_table_statements: list[str] = [self.DROP_TABLE_SQL.format(table_name) for table_name in self.TABLE_NAMES]
        self.create_table_statements: list[str] = [self.CREATE_SONG_REQUESTS_SQL, self.CREATE_SONG_PLAYS_SQL]

    async def initialize(self) -> None:
        async with aiosqlite.connect(self.database_file_path) as conn:
            if self.reset_database:
                print("Dropping tables")
                for drop_table_statement in self.drop_table_statements:
                    try:
                        await conn.execute(drop_table_statement)
                    except aiosqlite.Error as e:
                        print(f"Error in SQL statement {drop_table_statement}: " + str(e))

            for create_table_statement in self.create_table_statements:
                try:
                    await conn.execute(create_table_statement)
                except aiosqlite.Error as e:
                    print(f"Error in SQL statement {create_table_statement}: " + str(e))
    
    async def insert_song_request(self, song_request: tuple[datetime, int, int, str]) -> None:
        async with aiosqlite.connect(self.database_file_path) as conn:
            try:
                await conn.execute(self.INSERT_SONG_REQUEST_SQL, song_request)
            except aiosqlite.Error as e:
                print(f"Error in SQL statement {self.INSERT_SONG_REQUEST_SQL} with values {song_request}: " + str(e))
    
    async def insert_song_play(self, song_play: tuple[datetime, int, int, str, int]) -> None:
        async with aiosqlite.connect(self.database_file_path) as conn:
            try:
                await conn.execute(self.INSERT_SONG_PLAY_SQL, song_play)
            except aiosqlite.Error as e:
                print(f"Error in SQL statement {self.INSERT_SONG_PLAY_SQL} with values {song_play}: " + str(e))
    
    # TODO: CURRENT PLAN FOR STATS EMBEDS/DATABASE
    # Create embed in SongQueue object to be consistent with Song embed and future Stats embeds
    # Add guild id to song requests and plays to add support for multiple servers and to be consistent with audio_players in MusicCog
    # Separate classes for Stats and MusicDatabase: 
    # Stats has instance of MusicDatabase and uses it to get stats data, then transforms it into a discord embed
    # Stats class also creates graphs, which can be embedded
    # add argument parsing logic to stats command in MusicCog to get stats for song, user, or everything
    # may share logic with already existing argument parsing logic for the play command, reuse code as necessary
    async def get_song_requests(self, guild_id: int, requester_id: int = None, song_id: str = None) -> list[tuple[datetime, int, int, str]]:
        async with aiosqlite.connect(self.database_file_path) as conn:
            query = f"{self.SELECT_FROM_TABLE_BASE_SQL.format('song_requests')} {self.GUILD_ID_WHERE_CLAUSE.format(guild_id)}"
            if requester_id
            if requester_id:
                query += f" {self.REQUESTER_ID_WHERE_CLAUSE.format(requester_id)}"
            if song_id:
                query += f" {self.SONG_ID_WHERE_CLAUSE.format(song_id)}"
            query += 
            cursor = await conn.execute(query)
            song_requests = cursor.fetchall()
            return song_requests
    
    async def get_song_plays(self, guild_id: int, requester_id: int = None, song_id: str = None) -> list[tuple[datetime, int, int, str, int]]:
        async with self.async_session() as session:
            query = select(SongPlay).where(SongPlay.guild_id == guild_id)
            if requester_id and song_id:
            if requester_id:
                query = query.where(SongPlay.requester_id == requester_id)
            if song_id:
                query = query.where(SongPlay.song_id == song_id)
            result = await session.execute(query)
            song_plays = result.scalars()
            return song_plays

    async def execute_sql_statement(self, sql_statement: str) -> None:
        async with aiosqlite.connect(self.database_file_path) as conn:
            try:
                await conn.execute(sql_statement)
            except aiosqlite.Error as e:
                print(f"Error in SQL statement {sql_statement}: " + str(e))