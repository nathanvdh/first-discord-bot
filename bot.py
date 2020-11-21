import discord
from discord.ext import commands
import typing
import checks

#load default extensions
initial_extensions = [	'cogs.greetings',
						'cogs.botconfig',
						'cogs.errorhandler'
					 ]

bot = commands.Bot(command_prefix='!', description='A bot by nacho')

@bot.event
async def on_ready():
    print(f'\n\nLogged in as: {bot.user.name} - {bot.user.id}\nVersion: {discord.__version__}\n')

#only default command is ping
@bot.command()
async def ping(ctx, times: typing.Optional[int] = 1):
	reply = " ".join(['pong']*(times))
	await ctx.send(reply)

#bot is only used in bot channel
@bot.check
async def bot_channel(ctx):
	return ctx.channel == ctx.bot.get_channel(740557444417192037)

if __name__ == '__main__':
    for extension in initial_extensions:
        bot.load_extension(extension)

bot.run('NzQwMDg4MDg1OTg3MTk2OTc4.Xyj6vQ.KTmr0ar9mgroZuhHvX5JuxJX-xI', bot=True)