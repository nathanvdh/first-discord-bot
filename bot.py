import discord
from discord.ext import commands
import asyncio
import db

##specify default extensions
initial_extensions = [	'cogs.errorhandler',
						'cogs.botconfig',
						'cogs.greetings',
						'cogs.dad',
						'cogs.notes'
					 ]

bot = commands.Bot(command_prefix='!', description='A bot by nacho')

@bot.event
async def on_ready():
    print(f'\nLogged in as: {bot.user.name} - {bot.user.id}\nVersion: {discord.__version__}\n')

##only default command is ping
@bot.command()
async def ping(ctx):
	await ctx.send(pong)

##bot is only used in bot channel
@bot.check
async def bot_channel(ctx):
	bot_channels = [ctx.bot.get_channel(740557444417192037), ctx.bot.get_channel(779607758826635314)]
	
	return ctx.channel in bot_channels

if __name__ == '__main__':
    for extension in initial_extensions:
        bot.load_extension(extension)

with open("token.txt", "r") as token_file:
	token = token_file.read()

bot.run(token, bot=True)