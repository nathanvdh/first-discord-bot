import discord
from discord.ext import commands
import asyncio
import db
import checks

intents = discord.Intents.default()
intents.members = True

##specify default extensions
initial_extensions = [	'cogs.errorhandler',
						'cogs.botconfig',
						'cogs.dad',
						'cogs.notes',
						'cogs.moderation',
						'cogs.decide',
						'cogs.musicquiz'
					 ]

with open("owner.txt", "r") as owner_file:
	owner = owner_file.read()

async def get_prefix(bot, message):
	prefix = '!'
	if message.guild is None:
		pass
	else:
		_prefix = bot.prefixes[message.guild.id]
		#_prefix = await db.fetchfield("SELECT prefix FROM prefixes WHERE guild_id =?;", (message.guild.id,))
		if _prefix:
			prefix = _prefix
	return commands.when_mentioned_or(prefix)(bot, message)

class MyBot(commands.Bot):
	def __init__(self):
		super().__init__(command_prefix=get_prefix, description='A bot by nacho', owner_id=int(owner), intents=intents)
		self.prefixes = {}
		self.allowed_channels = {}
		self.loop.create_task(self.load_from_db())

	async def load_from_db(self):
		"""Loads necessary data from db to avoid queries on every message"""
		# Guild prefixes
		guilds = await db.fetchall("SELECT guild_id, prefix FROM prefixes")
		for guild in guilds:
			self.prefixes[guild[0]] = guild[1]

		# Guild bot channels
		bot_channels = await db.fetchall("SELECT guild_id, channel_id FROM bot_channels;")
		for bot_channel in bot_channels:
			self.allowed_channels.setdefault(bot_channel[0], []).append(bot_channel[1])




bot = MyBot()

@bot.event
async def on_ready():
	print(f'\nLogged in as: {bot.user.name} - {bot.user.id}\nVersion: {discord.__version__}\n')

@bot.event
async def on_guild_join(guild):
	await db.write("INSERT INTO prefixes (guild_id) VALUES (?)", (guild.id,))
	channel = guild.system_channel
	if channel is not None:
			await channel.send('Hide yo wife, hide yo kids. Diddly Kong is here!')

##only default command is ping
@bot.command(aliases=['latency'])
async def ping(ctx):
	await ctx.send(f'{round(bot.latency*1000)} ms')

bot.add_check(checks.bot_channel_only)

if __name__ == '__main__':
	for extension in initial_extensions:
		bot.load_extension(extension)

with open("token.txt", "r") as token_file:
	token = token_file.read()

bot.loop.create_task(db.build())
bot.run(token)