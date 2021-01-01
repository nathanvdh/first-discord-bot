from discord.ext import commands
import db

class NotInBotChannel(commands.CheckFailure):
	pass

async def bot_channel_only(ctx):
	if ctx.guild is None:
		if ctx.invoked_with == "help":
			return True
		else:
			raise NotInBotChannel()
	try:	
		bot_channel_ids = ctx.bot.allowed_channels[ctx.guild.id]
	except:
		return True
	if not bot_channel_ids:
		return True
	if ctx.channel.id in bot_channel_ids:
		return True
	raise NotInBotChannel()