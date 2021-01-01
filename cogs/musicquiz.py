import discord
from discord.ext import commands

import asyncio
from async_timeout import timeout
from aioconsole import ainput

from functools import partial

from contextlib import suppress

import db

import random

from fuzzywuzzy import fuzz
from fuzzywuzzy import process

from unidecode import unidecode

from async_spotify import SpotifyApiClient, TokenRenewClass
from async_spotify.authentification.authorization_flows import AuthorizationCodeFlow

class SpotifyTrackSource(discord.PCMVolumeTransformer):
	def __init__(self, track_data):
		super().__init__(discord.FFmpegPCMAudio(track_data['preview_url'], before_options='-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'))
		# Dict holding track_name: list of users who have guessed it
		self.track_name = unidecode(track_data['name'].casefold()).replace('(',' - ').split(" - ",1)[0]
		self.guessed_track = []
		# Dict holding artist_name: list of users who have guessed it
		self.artist_names = {artist_name: [] for artist_name in [unidecode(artist['name'].casefold()) for artist in track_data['artists']]}
		self.primary_artist = next(iter(self.artist_names.keys()))
		self.spotify_link = track_data['external_urls']['spotify']
		self.bonuses_given = 0
		# images = track_data['album']['images']
		# if images:
		# 	self.album_art = images[0]['url']

class QuizGame:
	"""An instance of a single running music trivia quiz game"""
	__slots__ = ('bot', '_no_tracks', '_artists', '_participants', '_guild', '_channel', '_cog', 'queue', '_guess_queue', 'next', '_track_ready', '_tracks_played', 'volume', 'current_track', '_tasks')
	
	def __init__(self, ctx, no_tracks: int, artists, participants=[]):
		self.bot = ctx.bot
		self._guild = ctx.guild
		self._channel = ctx.channel
		self._cog = ctx.cog
		
		self._no_tracks = no_tracks
		self._artists = artists
		self._participants = {participant: 0 for participant in participants}

		self.queue = asyncio.Queue()
		self._guess_queue = asyncio.Queue()
		self.next = asyncio.Event()
		self._track_ready = asyncio.Event()
		self._tracks_played = 0 ;
		self.current_track = None

		self.volume = .5
	
		self._tasks = []

	async def queue_tracks(self):
		"""Picks tracks from spotify and queues them"""
		artist_tracks = {}
		for i in range(0, self._no_tracks):
			artist = random.choice(self._artists)

			if not artist_tracks.get(artist):
				result = await self._cog.spy_client.artists.get_top_tracks(artist_id=artist, country='AU', limit=7)
				top_tracks = result['tracks']
				random.shuffle(top_tracks)
				artist_tracks[artist] = top_tracks

			track = artist_tracks[artist].pop()
			while not track['preview_url'] and artist_tracks.get(artist):
				print(f'Track {track["name"]} from artist {track["artists"][0]["name"]} does not have a 30s clip.')
				track = artist_tracks[artist].pop()
			
			if not artist_tracks.get(artist):
				await self._channel.send(f'None of the top tracks from {track["artists"][0]["name"]} have 30s clips :frowning:, consider removing them from rotation.')
				self._artists.remove(artist)
				continue

			source = SpotifyTrackSource(track)
			await self.queue.put(source)
	
	async def player_loop(self):
		"""Our main player loop."""
		await self.bot.wait_until_ready()
		for participant in self._participants:
				await participant.send('Welcome to Diddly Binb!\nThe game will begin in 10s...')
		
		while not self.bot.is_closed() and self._tracks_played != self._no_tracks and self._guild.voice_client:
			self.next.clear()
			self._track_ready.clear()
			await asyncio.sleep(10)
			try:
				# Wait for the next song. If we timeout cancel the player and disconnect...
				async with timeout(30):  # 30 seconds...
					source = await self.queue.get()
			except asyncio.TimeoutError:
				return self.end_queue_complete(self._guild)

			self.current_track = source
			self._track_ready.set()
			answer = f'Track name: {self.current_track.track_name}\n Artists: {self.current_track.artist_names}'
			print(answer)
			source.volume = self.volume
			self._guild.voice_client.play(source, after=lambda _: self.bot.loop.call_soon_threadsafe(self.next.set))
			await self.next.wait()

			# Make sure the FFmpeg process is cleaned up.
			source.cleanup()
			self._tracks_played += 1
			
			participants = self._participants
			participant_score_list = sorted(participants.items(), key=lambda item: item[1])
			after_track_str = 'Leaderboard:\n'
			for participant, score in participant_score_list:
				after_track_str += f'{participant.name}:\t\t {score}\n'
			after_track_str += f'The previous song was:\n{source.spotify_link}'
			
			for participant in participants:
				await participant.send(after_track_str)

		return self.end_queue_complete(self._guild)

	async def listen_to_participants(self):
		"""Handles messages sent in DMs, scoring and going to next song (maybe)"""
		def participant(msg):
			#print(msg.guild)
			return msg.author in self._participants and not msg.guild
		
		await self._track_ready.wait()
		
		while not self.bot.is_closed() and self._tracks_played != self._no_tracks and self._guild.voice_client:

			await self._guess_queue.put(await self.bot.wait_for('message', check=participant))
			print("Received and queued message\n")
	
	async def process_guesses(self):
		while not self.bot.is_closed() and self._tracks_played != self._no_tracks and self._guild.voice_client:
			print("Waiting for new guess to be queued")
			msg = await self._guess_queue.get()
			print("Processing guess")
			msg_content = msg.content.casefold()
			author = msg.author
			score = 0
			
			# Try to match track name
			string_match = partial(fuzz.ratio, msg_content, self.current_track.track_name)
			track_score = await self.bot.loop.run_in_executor(None, string_match)
			if track_score > 90 and author not in self.current_track.guessed_track:
				print(f'Track score: {track_score}\n')
				await msg.author.send('You guessed the song name!')
				self.current_track.guessed_track.append(author)
				score += 1
				
				bonuses_given = self.current_track.bonuses_given
				if bonuses_given < 3:
					if author in next(iter(self.current_track.artist_names.values())):
						score += 3 - bonuses_given
						self.current_track.bonuses_given += 1
				self._participants[author] += score
				continue

			# Try to match artist
			string_match = partial(process.extractOne, msg_content, self.current_track.artist_names.keys(), scorer=fuzz.ratio)
			artist, artist_score = await self.bot.loop.run_in_executor(None, string_match)
			# If the author hasn't guessed it already
			if artist_score > 90 and author not in self.current_track.artist_names[artist]:
				print(f'Artist score: {artist_score}\n')
				await msg.author.send('You guessed an artist!')
				# Add the author to the list of participants who have guessed the track
				self.current_track.artist_names[artist].append(author)
				
				score += 1
				if artist == self.current_track.primary_artist:
					bonuses_given = self.current_track.bonuses_given
					if bonuses_given < 3:
						if author in self.current_track.guessed_track:
							score += 3 - bonuses_given
							self.current_track.bonuses_given += 1
				self._participants[author] += score

	async def begin(self):
		"""Runs the other 3 loops?"""

		##queue_tracks() is a one-shot
		self.bot.loop.create_task(self.queue_tracks())
		
		loops = [self.player_loop(), self.listen_to_participants(), self.process_guesses()]
		for loop in loops:
			self._tasks.append(self.bot.loop.create_task(loop))

	def end_queue_complete(self, guild):
		"""Disconnect and cleanup the player internal"""
		## Only cancels the listen_to_participant loop as the player_loop returns (is done) after this function returns
		self._tasks[1].cancel()
		# Maybe don't cancel this to let the queue finish
		#self._tasks[2].cancel()
		return self.bot.loop.create_task(self._cog.cleanup(guild))

	def end_stopped(self, guild):
		"""Disconnect and cleanup the player external"""
		## Cancel both loops
		for task in self._tasks:
			task.cancel()
		return self.bot.loop.create_task(self._cog.cleanup(guild))

class MusicQuiz(commands.Cog, name='musicquiz'):
	"""A binb clone in a discord bot!"""
	
	#__slots__ = ('bot', 'games')

	def __init__(self, bot):
		self.bot = bot
		self.games = {}

		auth_flow=AuthorizationCodeFlow(scopes=[])
		auth_flow.load_from_env()
		api_client = SpotifyApiClient(auth_flow, hold_authentication=True, token_renew_instance = TokenRenewClass())
		
		self.spy_client = api_client
		
		bot.loop.create_task(self.create_tables())
		bot.loop.create_task(self.connect_to_spotify())

	def cog_unload(self):
		self.bot.loop.create_task(self.spy_client.close_client())
		for game in self.games.keys():
			del game

	async def on_command_error(self, ctx, error):
		
		if hasattr(ctx.command, 'on_error'):
			return
		
		error = getattr(error, 'original', error)
		
		if hassattr(error, 'message'):
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
		print("Cog cleanup done.")

	async def connect_to_spotify(self):
		authorization_url: str =  self.spy_client.build_authorization_url(show_dialog = False)
		print(f'Get auth code from here: {authorization_url}')
		code = await ainput('Paste the code here: ')
		await self.spy_client.get_auth_token_with_code(code)
		await self.spy_client.create_new_client()

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
				 )
				 """
		await db.writescript(sql)

	async def search_artist(self, artist_name: str):
		"""Searches for a single spotify artist and returns the first match"""
		search = await self.spy_client.search.start(query=f'{artist_name}', query_type=['artist'])
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
		artist_names_list= ['%'+artist_name+'%' for artist_name in artist_names_list]
		artists_data = []
		
		for artist_name in artist_names_list:
			sql = """SELECT artist_id, name, spotify_link, image_link FROM artists WHERE name LIKE ?"""
			artists_data.append(await db.fetchrow(sql, (artist_name,)))

		return artists_data

	async def add_to_category(self, category_name: str, artist_id_list, guild_id: int):
		#artists_data = await self.get_artists_from_db(artist_names_list)

		artist_cats_data = []
		for artist_id in artist_id_list:
			if artist_id:
				artist_cats_data.append((artist_id, category_name, guild_id))
		sql = """INSERT OR IGNORE INTO artist_cats (artist_id, category, guild_id)
				 VALUES (?, ?, ?)
			  """
		await db.write_multi_row(sql, artist_cats_data)
		#return filter(None, artists_data)

	async def get_artists_in_category(self, category_name: str, guild_id: int):
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

	# @commands.command()
	# async def artist(self, ctx, *, artist_name: str):
	# 	"""Gets artist info via spotify api"""

	# 	artist = await self.search_artist(artist_name)
	# 	top_tracks = await self.spy_client.artists.get_top_tracks(artist_id=artist['id'], country='AU', limit=7)
	# 	songs = ''
	# 	for track in top_tracks['tracks']:
	# 		songs += f'[{track["name"]}]({track["external_urls"]["spotify"]})\n'
	# 	embed = discord.Embed (
	# 		title = artist['name'],
	# 		url = artist['external_urls']['spotify'],
	# 	)
	# 	embed.set_thumbnail(url=f'{artist["images"][0]["url"]}')
	# 	embed.add_field(name='Top Songs', value=songs)
	# 	await ctx.send(embed=embed)

	# @commands.group(invoke_without_command=True)
	# async def play(self, ctx):
	# 	await ctx.send_help(ctx.command)

	# @play.command()
	# async def top(self, ctx, artist_name: str):
	# 	artist = await self.search_artist(artist_name)
	# 	top_tracks = await artist.get_top(limit=8)
	# 	preview = top_tracks[0].preview
	# 	source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(f'{preview}'))
	# 	ctx.voice_client.play(source, after=partial(self.leave_after,ctx=ctx))

	@commands.group(invoke_without_command=True, aliases=['mq'])
	async def musicquiz(self, ctx):
		"""Control the music guessing game"""
		await ctx.send_help(ctx.command)

	@commands.has_guild_permissions(manage_messages=True)	
	@musicquiz.command()
	async def add(self, ctx, category_name: str, *, artist_list:str):
		"""Add artists to a music category"""
		category_name = category_name.lower()
		artist_list_list = self.parse_csl(artist_list)
		if not self.valid_category(category_name):
			return

		#Lookup each artist and make a db entry
		##TODO: Skip artists that are already in the database
		##Currently spotify will be queried for every add command, even if artist already exists in db
		##Do this with some sqlite query that will return a list of artist names that don't match any in the db
		##artist_list_list = await self.remove_existing_artists(artist_list_list)
		artist_data = await self.add_new_artists(category_name, artist_list_list)
		await self.add_to_category(category_name, [artist[0] for artist in artist_data], ctx.guild.id)
		
		artists_str='Artists added:\n'
		for artist in artist_data:
			artists_str += f'{artist[1]}    '
		if not artists_str:
			artists += 'None'
		# embed = discord.Embed (
		# 	title = f'{ctx.author.name} added the following artists to the "{category_name}" category:',
		# )
		# embed.add_field(name='Added artists:', value=artists_str)

		await ctx.send(artists_str)
	
	@commands.has_guild_permissions(manage_guild=True)
	@musicquiz.group(invoke_without_command=True)
	async def remove(self, ctx, category_name: str, *, artist_list: str=""):
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

			artist_id_cat_list = [(artist[0], category_name, ctx.guild.id) for artist in artist_data]
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
	async def list(self, ctx, category_name: str=""):
		"""List the artists in a music category"""
		category_name = category_name.lower()

		if not category_name:
			sql = """SELECT DISTINCT category
					 FROM artist_cats
					 WHERE guild_id = ?
					 ORDER BY category ASC;
				  """
			guild_categories = await db.fetchcolumn(sql, (ctx.guild.id,))
			await ctx.send('MusicQuiz categories:\n' + '\n'.join(guild_categories))
		else:
			sql = """SELECT a.* 
					 FROM artists a
					 INNER JOIN artist_cats c ON a.artist_id = c.artist_id
					 WHERE category = ? AND guild_id = ?
					 ORDER BY a.name;
				  """
			vals = (category_name, ctx.guild.id)
			artist_list = await db.fetchall(sql, vals)
			if not artist_list:
				await ctx.send('That category does not exist!')
				return
			artists_str=''
			for artist in artist_list:
				artists_str += f'{artist[1]}    '

			# embed = discord.Embed (
			# 	title = f'The following artists are in the "{category_name}" category:',
			# )
			# embed.add_field(name=f'"{category_name}" artists:', value=artists_str)
			await ctx.send(artists_str)

	@musicquiz.command()
	async def start(self, ctx, category_name: str, no_songs: int):
		"""Starts a music trivia game
		Parameters:
		------------
		category_name : the category you want artists to be chosen from
		no_songs : the number of songs you want the game to last
		"""
		if self.games.get(ctx.guild.id):
			return ctx.send("A game is already in progress!")

		if not 1 <= no_songs <= 15:
			self.cleanup(ctx.guild)
			return ctx.send("Must provide a number of songs from 1 to 15") 

		category_name = category_name.lower()
		artists = await self.get_artists_in_category(category_name, ctx.guild.id)
		
		if not artists:
			self.cleanup(ctx.guild)
			return ctx.send("The provided category does not exist")
		
		participants = ctx.voice_client.channel.members
		participants.remove(ctx.me)

		game = QuizGame(ctx, no_songs, artists, participants)
		self.games[ctx.guild.id] = game

		await game.begin()

	@commands.command()
	async def stop(self, ctx):
		"""Stop the an in-progress music quiz"""
		vc = ctx.voice_client

		if not vc or not vc.is_connected():
			return await ctx.send('I am not currently playing anything!', delete_after=20)

		try:
			self.games[ctx.guild.id].end_stopped(ctx.guild)
		except KeyError:
			await self.cleanup(ctx.guild)



	@start.before_invoke
	async def ensure_voice(self, ctx):
		if ctx.voice_client is None:
			if ctx.author.voice:
				await ctx.author.voice.channel.connect()
			else:
				await ctx.send('Join a voice channel first.')
				raise commands.CommandError('Author not connected to a voice channel.')
		elif ctx.voice_client.is_playing():
			ctx.voice_client.stop()

	# def leave_after(self, error, ctx):
	# 	coro = ctx.voice_client.disconnect()
	# 	fut = asyncio.run_coroutine_threadsafe(coro, self.bot.loop)
	# 	try:
	# 		fut.result()
	# 	except:
	# 		pass

def setup(bot):
	bot.add_cog(MusicQuiz(bot))
