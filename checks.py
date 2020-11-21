import discord
from discord.ext import commands
from discord.utils import get
    
bot_channel_id = 740557444417192037

class NotInBotChannel(commands.CheckFailure):
    pass

class NotAdmin(commands.CheckFailure):
	pass

def bot_channel_only(ctx):
    if ctx.channel == ctx.bot.get_channel(bot_channel_id):
        return True
    raise NotInBotChannel()

def is_admin(ctx):
	admin = get(ctx.guild.roles, name='Admin')
	if admin not in ctx.author.roles:
		raise NotAdmin()
	return True