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

db_init = '''CREATE TABLE IF NOT EXISTS guild_prefs (
	guild_id integer PRIMARY KEY,
	prefix text DEFAULT "!",
	bot_channels text DEFAULT ""
)'''

with open("owner.txt", "r") as owner_file:
	owner = owner_file.read()

async def get_prefix(bot, message):
	prefix = await db.fetchone("SELECT prefix FROM guild_prefs WHERE guild_id =?;", (message.guild.id,))
	return commands.when_mentioned_or(prefix)(bot, message)

bot = commands.Bot(command_prefix=get_prefix, description='A bot by nacho', owner_id=int(owner))

@bot.event
async def on_ready():
    print(f'\nLogged in as: {bot.user.name} - {bot.user.id}\nVersion: {discord.__version__}\n')

@bot.event
async def on_guild_join(guild):
	await db.write("INSERT INTO guild_prefs (guild_id) VALUES (?)", (guild.id,))
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

async def run():
	await db.write(db_init)
	try:
		await bot.start(token)
	except KeyboardInterrupt:
		await bot.logout()


loop = asyncio.get_event_loop()
loop.run_until_complete(run())