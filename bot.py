import discord
from discord.ext import commands
import asyncio
import db
import checks

##specify default extensions
initial_extensions = [	'cogs.errorhandler',
						'cogs.botconfig',
						'cogs.dad',
						'cogs.notes',
						'cogs.moderation'
					 ]

with open("owner.txt", "r") as owner_file:
	owner = owner_file.read()

async def get_prefix(bot, message):
	prefix = '!'
	if message.guild is None:
		pass
	else:
		_prefix = await db.fetchfield("SELECT prefix FROM prefixes WHERE guild_id =?;", (message.guild.id,))
		if _prefix:
			prefix = _prefix
	return commands.when_mentioned_or(prefix)(bot, message)

bot = commands.Bot(command_prefix=get_prefix, description='A bot by nacho', owner_id=int(owner))

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