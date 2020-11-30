from discord.ext import commands
import db

class NotInBotChannel(commands.CheckFailure):
	pass

async def bot_channel_only(ctx):
	if ctx.guild is None:
		if ctx.invoked_with == "help":
			return True
	bot_channel_ids = await db.fetchall("SELECT channel_id FROM bot_channels WHERE guild_id = ? ;",(ctx.guild.id,))
	bot_channel_ids_list = [x[0] for x in bot_channel_ids]
	if not bot_channel_ids_list
		return True
	if ctx.channel.id in bot_channel_ids_list:
		return True
	raise NotInBotChannel()