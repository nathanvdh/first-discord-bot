import discord
from discord.ext import commands
from discord.utils import get
    
bot_channel_ids = (740557444417192037, 779607758826635314)

class NotInBotChannel(commands.CheckFailure):
    pass

class NotAdmin(commands.CheckFailure):
	pass

def bot_channel_only(ctx):
    if ctx.guild is None:
    	if ctx.invoked_with == "help":
    		return True
    if ctx.channel in map(ctx.bot.get_channel, bot_channel_ids):
        return True
    raise NotInBotChannel()

def is_admin(ctx):
	admin = get(ctx.guild.roles, name='Admin')
	if admin not in ctx.author.roles:
		raise NotAdmin()
	return True