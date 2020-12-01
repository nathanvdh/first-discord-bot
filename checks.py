from discord.ext import commands
import db

class NotInBotChannel(commands.CheckFailure):
	pass

async def bot_channel_only(ctx):
	if ctx.guild is None:
		if ctx.invoked_with == "help":
			return True
	bot_channel_ids = await db.fetchcolumn("SELECT channel_id FROM bot_channels WHERE guild_id = ? ;",(ctx.guild.id,))
	if not bot_channel_ids:
		return True
	if ctx.channel.id in bot_channel_ids:
		return True
	raise NotInBotChannel()