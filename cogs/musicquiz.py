import discord
from discord.ext import commands

import asyncio
from async_timeout import timeout

from functools import partial

from aioconsole import ainput

import random

import time as t

import math
import Levenshtein as lev

import db

from async_spotify import SpotifyApiClient, TokenRenewClass
from async_spotify.authentification.authorization_flows import AuthorizationCodeFlow
from async_spotify import spotify_errors

from unidecode import unidecode
import sys

from string_lists import replace_list, goodbyes


class SpotifyTrackSource(discord.PCMVolumeTransformer):
    def __init__(self, track_data):
        super().__init__(discord.FFmpegPCMAudio(track_data['preview_url'],
                                                before_options='-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'))
        # Dict holding track_name: list of users who have guessed it
        track_name = unidecode(track_data['name'].casefold()).replace('(', ' - ').split(" - ", 1)[0]
        for find, repl in replace_list:
            track_name = track_name.replace(find, repl)
        self.track_name = track_name
        self.guessed_track = []
        # Dict holding artist_name: list of users who have guessed it
        artist_names = []
        for artist in track_data['artists']:
            artist_name = unidecode(artist['name'].casefold())
            for find, repl in replace_list:
                artist_name = artist_name.replace(find, repl)
            artist_names.append(artist_name)

        self.artist_names = {artist_name: [] for artist_name in artist_names}
        self.primary_artist = next(iter(self.artist_names.keys()))
        self.spotify_link = track_data['external_urls']['spotify']
        self.bonuses_given = 0


class QuizGame:
    """An instance of a single running music trivia quiz game"""
    __slots__ = (
        'bot', '_guild', '_channel', '_cog', '_playlist_id', '_no_tracks', '_artists', '_participants', '_in_progress',
        'queue', '_guess_queue', 'next', '_track_ready', 'current_track', '_track_start_time', 'volume', '_tasks',
        'sending_to_all', '_refused_members')

    def __init__(self, ctx, no_tracks: int, artists=None, in_channel=None, playlist_id=None):
        if in_channel is None:
            in_channel = []

        self.bot = ctx.bot
        self._guild = ctx.guild
        self._channel = ctx.channel
        self._cog = ctx.cog
        self._playlist_id = playlist_id

        self._no_tracks = no_tracks
        self._artists = artists
        self._participants = {}
        self._refused_members = []

        self._in_progress = True
        self.queue = asyncio.Queue()
        self._guess_queue = asyncio.Queue()
        self.next = asyncio.Event()
        self._track_ready = asyncio.Event()
        self.sending_to_all = asyncio.Event()
        # self._tracks_played = 0 ;
        self.current_track = None
        self._track_start_time = 0.0

        self.volume = .5

        self._tasks = []
        for member in in_channel:
            ctx.bot.loop.create_task(self.process_join(member))

    async def queue_tracks(self):
        """Picks tracks from spotify and queues them"""
        if self._playlist_id:
            try:
                all_tracks = await self.bot.spy_client.playlists.get_tracks(playlist_id=self._playlist_id, country='AU',
                                                                            fields='items(track)')
            except spotify_errors.SpotifyAPIError:
                error_str = "Could not get the tracks from that playlist"
                print(error_str)
                await self._channel.send(error_str)
                return await self.bot.loop.run_in_executor(None, self.end_stopped, self._guild)

            # print(all_tracks)
            all_tracks_extracted = [thing["track"] for thing in all_tracks["items"]]
            random.shuffle(all_tracks_extracted)
            # print(all_tracks_extracted)

            for i in range(0, self._no_tracks):
                track = all_tracks_extracted.pop()
                while not track['preview_url'] and all_tracks_extracted:
                    print(f'Track {track["name"]} from artist {track["artists"][0]["name"]} does not have a 30s clip.')
                    track = all_tracks_extracted.pop()
                if not all_tracks_extracted:
                    print(f"There aren't enough tracks in the playlist to fill the queue!")
                    return

                print(f'Queued {track["artists"][0]["name"]} - {track["name"]}')
                source = SpotifyTrackSource(track)
                await self.queue.put(source)
        else:
            artist_tracks = {}
            for i in range(0, self._no_tracks):
                artist = random.choice(self._artists)
                if not artist_tracks.get(artist):
                    # print("Getting track from spotify")
                    result = await self.bot.spy_client.artists.get_top_tracks(artist_id=artist, country='AU', limit=7)
                    # print("Got track")
                    top_tracks = result['tracks'][:7]
                    random.shuffle(top_tracks)
                    artist_tracks[artist] = top_tracks

                track = artist_tracks[artist].pop()
                while not track['preview_url'] and artist_tracks.get(artist):
                    print(f'Track {track["name"]} from artist {track["artists"][0]["name"]} does not have a 30s clip.')
                    track = artist_tracks[artist].pop()

                if not artist_tracks.get(artist):
                    await self._channel.send(
                        f'None of the top tracks from {track["artists"][0]["name"]} have 30s clips :frowning:, consider removing them from rotation.')
                    self._artists.remove(artist)
                    continue

                print(f'Queued {track["artists"][0]["name"]} - {track["name"]}')
                source = SpotifyTrackSource(track)
                await self.queue.put(source)

    async def _send_all(self, all_message: str):
        self.sending_to_all.clear()
        for participant in self._participants.keys():
            if participant in self._guild.voice_client.channel.members:
                await participant.send(all_message, allowed_mentions=discord.AllowedMentions.none())
        self.sending_to_all.set()

    async def _send_goodbye(self):
        self.sending_to_all.clear()
        for participant in self._participants.keys():
            if participant in self._guild.voice_client.channel.members:
                await participant.send(random.choice(goodbyes), allowed_mentions=discord.AllowedMentions.none())
        self.sending_to_all.set()

    async def player_loop(self):
        """Main player loop."""
        # print("start of player loop")
        await self.bot.wait_until_ready()

        self.next.clear()
        self._track_ready.clear()
        _tracks_played = 0
        # print("waiting 5 seconds")
        await asyncio.sleep(5)
        while self.queue.empty():
            print("queue is still empty")
            await asyncio.sleep(1)
        while not self.bot.is_closed() and not self.queue.empty() and self._guild.voice_client:
            #print("waiting 10s")
            await asyncio.sleep(10)
            try:
                # Wait for the next song. If we timeout cancel the player and disconnect...
                async with timeout(30):  # 30 seconds...
                    # print("Getting next track")
                    source = await self.queue.get()
            except asyncio.TimeoutError:
                # print("Geting track timed out")
                return self.end_queue_complete(self._guild)

            self.current_track = source
            self._track_ready.set()

            # answer = f'Track name: {self.current_track.track_name}\n Artists: {self.current_track.artist_names.keys()}'
            # print(answer)
            source.volume = self.volume

            self._track_start_time = t.time()

            # print("Playing track")
            self._guild.voice_client.play(source, after=lambda _: self.bot.loop.call_soon_threadsafe(self.next.set))
            _tracks_played += 1
            await self.next.wait()
            # print("Song finished playing...")
            # Make sure the FFmpeg process is cleaned up.
            source.cleanup()

            self.next.clear()
            self._track_ready.clear()

            if not self._guess_queue.empty():
                queue_size = self._guess_queue.qsize()
                print(f"{queue_size} guesses remain in queue...waiting and then clearing")
                await asyncio.sleep(2)
                for _ in range(self._guess_queue.qsize()):
                    self._guess_queue.get_nowait()
                    self._guess_queue.task_done()

            # print("Sorting player data")
            participant_data_list = sorted(self._participants.items(), key=lambda item: item[1]['score'], reverse=True)
            after_track_str = '__**Leaderboard:**__\n\n'
            # print("Enumerating sorted player data")
            enum = enumerate(participant_data_list)
            place_prefix = ""
            # print("Looping through players")
            for place, participant_data in enum:
                participant, participant_data = participant_data
                if place == 0:
                    place_prefix = ":first_place:"
                elif place == 1:
                    place_prefix = ":second_place:"
                elif place == 2:
                    place_prefix = ":third_place:"

                after_track_str += f'{place_prefix}\t{participant.mention}:\t {participant_data["score"]}'
                gained = participant_data['gained']
                guess_time = participant_data['guesstime']

                if gained:
                    after_track_str += f'\t(+{gained})'
                if guess_time > 0:
                    after_track_str += f' ({guess_time}s)'
                after_track_str += '\n'

            after_track_str += f'\n*The previous song ({_tracks_played} of {self._no_tracks}) was:*\n{source.spotify_link}'
            await self._send_all(after_track_str)
            for participant in self._participants.keys():
                self._participants[participant]['gained'] = 0
                self._participants[participant]['guesstime'] = 0.0

        print("Player loop ended")
        await self._send_goodbye()
        await self.sending_to_all.wait()
        return self.end_queue_complete(self._guild)

    async def listen_to_participants(self):
        """Listens for particpant DMs and adds their guesses to the queue"""

        def participant(msg):
            return msg.author in self._participants.keys() and not msg.guild

        while self._in_progress:
            # print("inside listen_to_participants")
            await self._track_ready.wait()
            msg = await self.bot.wait_for('message', check=participant)
            # print("Received message\n")
            if self._track_ready.is_set():
                # print("Try to queue message\n")
                await self._guess_queue.put(msg)
                # print("Queued message\n")
        # print("Listen_to_participants ended")

    async def process_guesses(self):

        async def isMatch(target: str, guess: str):
            # print("isMatch start")
            thresh = round(math.log(len(target)))
            if thresh == 0:
                return target == guess
            # print("doing levdistance in bot loop")
            levdistance = partial(lev.distance, target, guess)
            dist = await self.bot.loop.run_in_executor(None, levdistance)
            # print(f'Comparing {guess} to: {target}\tthresh: {thresh} dist: {dist}')
            return dist <= thresh

        async def artistMatch(guess: str):
            # print('artistMatch start')
            for artist in self.current_track.artist_names.keys():
                artist_match = await isMatch(artist, guess)
                if artist_match:
                    return artist
            return None

        async def on_match(author: discord.Member, bArtist: bool = False, artist=None):
            async def guessed_both():
                # print("Someone guessed both")
                time_diff = round(t.time() - self._track_start_time, 2)
                self._participants[author]['guesstime'] = time_diff
                time_msg = ''
                author_mention = author.mention
                if time_diff < 5:
                    time_msg = f'Woah {author_mention} guessed it in {time_diff}s, what a nerd :nerd:'
                elif time_diff < 10:
                    time_msg = f'Great job{author_mention}! They guessed it in {time_diff}s'
                elif time_diff < 20:
                    time_msg = f'{author_mention} got it in {time_diff}s'
                elif time_diff < 30:
                    time_msg = f'Wow... {author_mention} finally got it but it took them {time_diff}s :snail:'
                await self._send_all(time_msg)
                bonuses_given = self.current_track.bonuses_given
                if bonuses_given < 3:
                    self.current_track.bonuses_given += 1
                    return 3 - bonuses_given
                return 0

            # print("on_match start")
            guess_score = 1

            artist_or_song = 'song'
            if bArtist:
                artist_or_song = 'artist'

            await author.send(f'You guessed the {artist_or_song} name!')
            # Process guessing the track right
            if not bArtist:
                self.current_track.guessed_track.append(author)
                if author in next(iter(self.current_track.artist_names.values())):
                    guess_score += await guessed_both()
            # Process guessing the artist right
            else:
                self.current_track.artist_names[artist].append(author)
                if artist == self.current_track.primary_artist:
                    if author in self.current_track.guessed_track:
                        guess_score += await guessed_both()
            self._participants[author]['score'] += guess_score
            self._participants[author]['gained'] += guess_score
            # print('finished processing guess')
            return

        async def compare_track(guess: str, author: discord.Member):
            match = await isMatch(self.current_track.track_name,
                                  guess)  # self.bot.loop.run_in_executor(None, title_match)
            if match:
                await on_match(author=author)
                return True
            else:
                return False

        async def compare_artists(guess: str, author: discord.Member):
            artist = await artistMatch(guess)  # self.bot.loop.run_in_executor(None, artist_match)
            if artist and author not in self.current_track.artist_names[artist]:
                await on_match(author=author, bArtist=True, artist=artist)
                return True
            else:
                return False

        while self._in_progress:
            # print("Waiting for new guess to be queued")
            msg = await self._guess_queue.get()
            # print("Processing guess")
            msg_content = msg.content.casefold()
            author = msg.author
            score = 0
            if ';' in msg_content:
                artist_name, track_name = msg_content.split(';')
                if author not in self.current_track.guessed_track:
                    await compare_track(track_name, author)
                    await compare_artists(artist_name, author)
                continue

            if author not in self.current_track.guessed_track:
                if await compare_track(msg_content, author):
                    continue
            # print("Didn't match song name\n")
            if await compare_artists(msg_content, author):
                continue
        # print("Didn't match an artist name\n")#Modifying input and retrying...\n")
        # print("left process_guesses loop")

    async def listen_for_joins(self):
        def check(member, before, after):
            if after.channel == self._guild.voice_client.channel:
                if member not in self._participants.keys():
                    if member not in self._refused_members:
                        return True

        while self._in_progress:
            # print("Waiting for player to join...")
            member, before, after = await self.bot.wait_for('voice_state_update', check=check)
            # print("New player joined!\n")
            await self.process_join(member)

    async def process_join(self, member):

        def check(reaction, user):
            return str(reaction.emoji) in ['🇾', '🇳'] and user == member

        try:
            msg = await member.send('Welcome to Diddly Binb! Would you like to play? (Y / N)\n15 seconds to decide....')
        except discord.Forbidden:
            return

        await msg.add_reaction('🇾')
        await msg.add_reaction('🇳')

        try:
            reaction, user = await self.bot.wait_for('reaction_add', check=check, timeout=15)
        except asyncio.TimeoutError:
            return
        else:
            if str(reaction.emoji) == '🇾':
                # print("Adding new member to game\n")
                self._participants[member] = {'score': 0, 'gained': 0, 'guesstime': 0.0}
                await member.send('Enjoy the game!')
            else:
                self._refused_members.append(member)
                await msg.delete()
                pass

    async def begin(self):
        """Runs the other tasks"""

        # queue_tracks() is a one-shot
        self.bot.loop.create_task(self.queue_tracks())

        loops = [self.player_loop(), self.listen_to_participants(), self.process_guesses(), self.listen_for_joins()]
        for loop in loops:
            self._tasks.append(self.bot.loop.create_task(loop))

    def end_queue_complete(self, guild):
        """Disconnect and cleanup the player internal"""
        # Don't cancel player_loop as it waits for return of this function
        self._in_progress = False
        # self.bot.loop.create_task()
        for task in self._tasks[1:]:
            task.cancel()
        return self.bot.loop.create_task(self._cog.cleanup(guild))

    def end_stopped(self, guild):
        """Disconnect and cleanup the player external"""
        self._in_progress = False
        # Cancel all loops
        for task in self._tasks:
            task.cancel()
        return self.bot.loop.create_task(self._cog.cleanup(guild))


class MusicQuiz(commands.Cog, name='musicquiz'):
    """A binb clone in a discord bot!"""

    # __slots__ = ('bot', 'games')

    def __init__(self, bot):
        self.bot = bot
        self.games = {}

        if not bot.spy_client:
            auth_flow = AuthorizationCodeFlow(scopes=[])
            auth_flow.load_from_env()
            api_client = SpotifyApiClient(auth_flow, hold_authentication=True, token_renew_instance=TokenRenewClass())
            bot.spy_client = api_client
            bot.loop.create_task(self.connect_to_spotify())

        bot.loop.create_task(self.create_tables())

    def cog_unload(self):
        for game in self.games.keys():
            del game

    async def on_command_error(self, ctx, error):

        if hasattr(ctx.command, 'on_error'):
            return

        error = getattr(error, 'original', error)

        if hasattr(error, 'message'):
            await ctx.send(f'{error.message}')

        else:
            print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

    async def cleanup(self, guild):
        try:
            await guild.voice_client.disconnect()
        except AttributeError:
            pass

        try:
            del self.games[guild.id]
        except KeyError:
            pass

    # print("Cog cleanup done.")

    async def connect_to_spotify(self):
        authorization_url: str = self.bot.spy_client.build_authorization_url(show_dialog=False)
        print(f'Get auth code from here: {authorization_url}')
        code = await ainput('Paste the code here: ')
        await self.bot.spy_client.get_auth_token_with_code(code)
        await self.bot.spy_client.create_new_client()

    async def create_tables(self):
        sql = """CREATE TABLE IF NOT EXISTS artists (
                 artist_id text PRIMARY KEY,
				 name text,
				 spotify_link text,
				 image_link text);

				 CREATE TABLE IF NOT EXISTS artist_cats (
				 artist_id text,
				 category text,
				 guild_id integer,
				 FOREIGN KEY (artist_id)
					REFERENCES artists (artist_id)
					ON DELETE CASCADE
				 UNIQUE (artist_id, category, guild_id)
				 ); 

				 CREATE TABLE IF NOT EXISTS tracks (
				 track_id integer PRIMARY KEY,
				 artist_id text,
				 track_title text,
				 mp3_path text,
				 FOREIGN KEY (artist_id)
					REFERENCES artists (artist_id)
					ON DELETE CASCADE
				 );
				 
				 CREATE TABLE IF NOT EXISTS playlists (
				 playlist_id text,
				 name text,
				 guild_id integer,
				 UNIQUE (playlist_id, name, guild_id)
				 )
				 """

        await db.writescript(sql)

    async def search_artist(self, artist_name: str):
        """Searches for a single spotify artist and returns the first match"""
        search = await self.bot.spy_client.search.start(query=f'{artist_name}', query_type=['artist'])
        return search['artists']['items'][0]

    async def add_new_artists(self, category_name: str, artist_names):
        """
		Gets artists and data from spotify and adds data to db
		Returns a list of tuples, each tuple is an artist in the following format: (artist_id, name, spotify_link, image_link)
		"""
        artist_data = []

        for artist_name in artist_names:
            artist = await self.search_artist(artist_name)
            images = artist['images']
            if images:
                image = images[0]['url']
            else:
                image = None
            artist_data.append((artist['id'], artist['name'], artist['external_urls']['spotify'], image))

        sql = """INSERT OR IGNORE INTO artists (artist_id, name, spotify_link, image_link)
				 VALUES (?, ?, ?, ?)
			  """
        await db.write_multi_row(sql, artist_data)

        return artist_data

    async def get_artists_from_db(self, artist_names_list):
        ##TODO: Make this search much much better
        artist_names_list = ['%' + artist_name + '%' for artist_name in artist_names_list]
        artists_data = []

        for artist_name in artist_names_list:
            sql = """SELECT artist_id, name, spotify_link, image_link FROM artists WHERE name LIKE ?"""
            artists_data.append(await db.fetchrow(sql, (artist_name,)))

        return artists_data

    async def add_to_category(self, category_name: str, artist_id_list, guild_id: int):
        # artists_data = await self.get_artists_from_db(artist_names_list)

        artist_cats_data = []
        for artist_id in artist_id_list:
            if artist_id:
                artist_cats_data.append((artist_id, category_name, guild_id))
        sql = """INSERT OR IGNORE INTO artist_cats (artist_id, category, guild_id)
				 VALUES (?, ?, ?)
			  """
        await db.write_multi_row(sql, artist_cats_data)

    # return filter(None, artists_data)

    async def get_artists_in_category(self, category_name: str, guild_id: int):
        if category_name == "all":
            sql = """SELECT DISTINCT artist_id FROM artist_cats
					 WHERE guild_id = ? ;
				  """
            vals = (guild_id,)
        else:
            sql = """SELECT artist_id FROM artist_cats
					WHERE category = ?
					AND guild_id = ? ;"""
            vals = (category_name, guild_id)

        return await db.fetchcolumn(sql, vals)

    def parse_csl(self, str_list: str):
        """
		Parses a comma separated list of values in a string, into a list
		"""
        the_list = str_list.strip(' ,').split(',')
        parsed_list = [item.strip() for item in the_list]

        if "" in parsed_list:
            raise commands.ArgumentParsingError("Provided list contains an empty item")

        return parsed_list

    def valid_category(self, category_name):
        if category_name in ("add", "remove", "delete", "list", "all", "info"):
            raise commands.ArgumentParsingError("Provided category name is banned")
        else:
            return True

    async def get_playlist_id(self, internal_name: str, guild_id: int):
        sql = """SELECT DISTINCT playlist_id FROM playlists
                 WHERE guild_id = ?
                 AND name = ?"""
        return await db.fetchfield(sql, (guild_id, internal_name))

    @commands.group(invoke_without_command=True, aliases=['mq'])
    async def musicquiz(self, ctx, category_name=""):
        """Control the music guessing game"""
        await ctx.send_help(ctx.command)

    @commands.has_guild_permissions(manage_channels=True)
    @musicquiz.group(invoke_without_command=True)
    async def add(self, ctx, category_name: str, *, artist_list: str):
        """Add artists to a music category"""
        category_name = category_name.lower()
        artist_list_list = self.parse_csl(artist_list)
        if not self.valid_category(category_name):
            return

        # Lookup each artist and make a db entry
        ##TODO: Skip artists that are already in the database
        ##Currently spotify will be queried for every add command, even if artist already exists in db
        ##Do this with some sqlite query that will return a list of artist names that don't match any in the db
        ##artist_list_list = await self.remove_existing_artists(artist_list_list)
        artist_data = await self.add_new_artists(category_name, artist_list_list)
        await self.add_to_category(category_name, [artist[0] for artist in artist_data], ctx.guild.id)

        artists_msg = 'Artists added:\n'
        artists_str = ''
        for artist in artist_data:
            artists_str += f'{artist[1]}    '
        if not artists_str:
            artists_str += 'None'
        artists_msg += artists_str
        # embed = discord.Embed (
        # 	title = f'{ctx.author.name} added the following artists to the "{category_name}" category:',
        # )
        # embed.add_field(name='Added artists:', value=artists_str)

        await ctx.send(artists_msg)

    @commands.has_guild_permissions(manage_channels=True)
    @add.command(name='playlist')
    async def add_playlist(self, ctx, playlist_id: str, *, playlist_name: str):

        ##TODO Get more information (e.g. link) and store in db, using self.bot.spy_client.playlists.get_one(playlist_id)
        playlist_name = playlist_name.lower()

        sql = """INSERT OR IGNORE INTO playlists (playlist_id, name, guild_id)
        				 VALUES (?, ?, ?)
        			  """
        await db.write(sql, (playlist_id, playlist_name, ctx.guild.id))
        await ctx.send('** {0} added a new playlist called {1} **'.format(ctx.author.name,playlist_name))

    @commands.has_guild_permissions(manage_channels=True)
    @musicquiz.group(invoke_without_command=True)
    async def remove(self, ctx, category_name: str, *, artist_list: str = ""):
        """Remove artists from a music category"""
        category_name = category_name.lower()
        sql = """SELECT EXISTS(SELECT 1 FROM artist_cats WHERE category = ? AND guild_id = ?) ;
			  """
        category_exists = await db.fetchfield(sql, (category_name, ctx.guild.id))

        if not category_exists:
            await ctx.send('That category does not exist!')
            return
        elif not artist_list:
            sql = """
					 DELETE FROM artist_cats
					 WHERE category = ?
					 AND guild_id = ? ;
				  """
            await db.write(sql, (category_name, ctx.guild.id))
            success = 'removed'
        else:
            artist_list_list = self.parse_csl(artist_list)

            artist_data = await self.get_artists_from_db(artist_list_list)
            artist_id_cat_list = []
            for artist in artist_data:
                if artist:
                    artist_id_cat_list.append((artist[0], category_name, ctx.guild.id))
                else:
                    print("Requested artist wasn't found")
            if not artist_id_cat_list:
                return
            sql = """DELETE FROM artist_cats
					 WHERE artist_id = ?
					 AND category = ?
					 AND guild_id = ? ;"""
            await db.write_multi_row(sql, artist_id_cat_list)
            success = 'modified'

        await ctx.send('**`{0} {1} group "{2}"`**'.format(ctx.author.name, success, category_name))

    @commands.is_owner()
    @remove.command(name='artists')
    async def remove_artists(self, ctx, *, artist_list: str):
        """
		You probably don't want to ENTIRELY remove artists from EVERY category for EVERY discord server.
		Hence, only the owner can do this. Should be used for cleaning the db or some special case.
		"""
        ##!mq remove artists [artist_list]
        ##TODO: Add warning
        artist_list_list = self.parse_csl(artist_list)

        sql = """DELETE FROM artists
				 WHERE name LIKE ?
			  """
        await db.write(sql, (artist_list_list))

    @musicquiz.command()
    async def list(self, ctx, *, category_name: str = ""):
        """List the artists in a music category"""
        category_name = category_name.lower()

        if not category_name:
            sql_cat = """SELECT DISTINCT category
					 FROM artist_cats
					 WHERE guild_id = ?
					 ORDER BY category ASC;
				  """
            guild_categories = await db.fetchcolumn(sql_cat, (ctx.guild.id,))

            sql_play = """SELECT DISTINCT name
                      FROM playlists
                      WHERE guild_id = ?
                      ORDER BY name ASC;"""

            guild_playlists = await db.fetchcolumn(sql_play, (ctx.guild.id,))
            list_str = 'MusicQuiz categories:\n' + '\n'.join(guild_categories)
            list_str += '\nMusicQuiz playlists:\n' + '\n'.join(guild_playlists)
            await ctx.send(list_str)

        else:
            if category_name == "all":
                sql = """SELECT a.*
						 FROM artists a
						 INNER JOIN artist_cats c ON a.artist_id = c.artist_id
						 WHERE guild_id = ?
						 ORDER BY a.name COLLATE NOCASE;
					  """
                vals = (ctx.guild.id,)
            else:
                sql = """SELECT a.* 
						 FROM artists a
						 INNER JOIN artist_cats c ON a.artist_id = c.artist_id
						 WHERE category = ? AND guild_id = ?
						 ORDER BY a.name COLLATE NOCASE;
					  """
                vals = (category_name, ctx.guild.id)

            artist_list = await db.fetchall(sql, vals)
            if not artist_list:
                str_playlist_id = await self.get_playlist_id(category_name, ctx.guild.id)
                if str_playlist_id:
                    await ctx.send(f'https://open.spotify.com/playlist/{str_playlist_id}')
                else:
                    await ctx.send('There is no category or playlist with that name')
                return
            artists_str = ''
            for artist in artist_list:
                artists_str += f'{artist[1]}    '

            await ctx.send(artists_str)

    @musicquiz.group(invoke_without_command=True)
    async def start(self, ctx, category_name: str, no_songs: int = 15):
        """Starts a music trivia game from a specified category or playlist
		Parameters:
		------------
		category_name : the category/playlist you want artists/songs to be chosen from
		                if this is multiple words, enclose in double quotes
		no_songs : the number of songs you want the game to last
		"""
        if self.games.get(ctx.guild.id):
            return ctx.send("A game is already in progress!")

        if not 1 <= no_songs <= 15:
            await ctx.send("Must provide a number of songs from 1 to 15")
            await self.cleanup(ctx.guild)
            return

        category_name = category_name.lower()
        artists = await self.get_artists_in_category(category_name, ctx.guild.id)

        in_channel = ctx.voice_client.channel.members
        in_channel.remove(ctx.me)

        if not artists:
            playlist_id = await self.get_playlist_id(category_name, ctx.guild.id)
            if not playlist_id:
                await ctx.send("Sorry, there is no category or playlist with that name")
                await self.cleanup(ctx.guild)
                return
            game = QuizGame(ctx, no_tracks=no_songs, in_channel=in_channel, playlist_id=playlist_id)
        else:
            game = QuizGame(ctx, no_tracks=no_songs, artists=artists, in_channel=in_channel)

        self.games[ctx.guild.id] = game
        await game.begin()

    @start.command()
    async def playlist(self, ctx, internal_name: str, no_songs: int = 15):
        """Starts a music trivia game from a playlist
                (only required if a category and playlist name clash)
		Parameters:
		------------
		internal_name : the playlist name the bot was supplied with
		no_songs : the number of songs you want the game to last
		"""
        if self.games.get(ctx.guild.id):
            return ctx.send("A game is already in progress!")

        if not 1 <= no_songs <= 15:
            await ctx.send("Must provide a number of songs from 1 to 15")
            await self.cleanup(ctx.guild)
            return
        playlist_id = await self.get_playlist_id(internal_name, ctx.guild.id)
        if not playlist_id:
            await ctx.send("Sorry, there is no playlist with that name")
            await self.cleanup(ctx.guild)
            return
        in_channel = ctx.voice_client.channel.members
        in_channel.remove(ctx.me)

        game = QuizGame(ctx, no_tracks=no_songs, in_channel=in_channel, playlist_id=playlist_id)
        self.games[ctx.guild.id] = game
        await game.begin()

    @musicquiz.command()
    async def stop(self, ctx):
        """Stop the an in-progress music quiz"""
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send('I am not currently playing anything!', delete_after=20)

        try:
            self.games[ctx.guild.id].end_stopped(ctx.guild)
        except KeyError:
            await self.cleanup(ctx.guild)

    @commands.is_owner()
    @musicquiz.command()
    async def skip(self, ctx):
        """Skips the currently playing track"""
        try:
            game = self.games[ctx.guild.id]
        except KeyError:
            ctx.send("A game is not currently active", delete_after=20)
            return
        vc = ctx.voice_client
        if not vc or not vc.is_connected():
            return await ctx.send('I am not currently playing anything!', delete_after=20)
        if vc.is_paused():
            pass
        elif not vc.is_playing():
            return
        vc.stop()

    @start.before_invoke
    @playlist.before_invoke
    async def ensure_voice(self, ctx):
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send('Join a voice channel first.')
                raise commands.CommandError('Author not connected to a voice channel.')
        elif ctx.voice_client.is_playing():
            ctx.voice_client.stop()


def setup(bot):
    bot.add_cog(MusicQuiz(bot))
