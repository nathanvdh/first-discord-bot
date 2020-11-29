import discord
from discord.ext import commands
import db

class Moderation(commands.Cog, name='moderation'):
	def __init__(self, bot):
		self.bot = bot

	@commands.group(invoke_without_command=True, name='set')
	async def settings(self, ctx):
		"""Manage server specific bot settings"""
		await ctx.send_help(ctx.command)

	@commands.has_guild_permissions(manage_channels=True)
	@settings.group(invoke_without_command=True)
	async def botchannel(self, ctx):
		"""Add/remove a channel users can use bot commands in"""
		await ctx.send_help(ctx.command)
	
	
	@botchannel.command()
	async def add(self, ctx, channel: discord.TextChannel):
		"""Allow a channel to use bot commands"""
		new_channel = str(channel.id)
		await db.write("UPDATE guild_prefs SET bot_channels = bot_channels || ? || ',' WHERE guild_id = ? ;", (new_channel, ctx.guild.id))

	@botchannel.command()
	async def remove(self, ctx, channel: discord.TextChannel):
		"""Disallow a channel to use bot commands"""
		rm_channel = str(channel.id)
		bot_channel_ids = await db.fetchone("SELECT bot_channels FROM guild_prefs WHERE guild_id = ? ;", (ctx.guild.id,))
		bot_channel_ids_new = bot_channel_ids.replace(rm_channel+',', '')
		print(bot_channel_ids_new)
		await db.write("UPDATE guild_prefs SET bot_channels = ? WHERE guild_id = ? ;", (bot_channel_ids_new, ctx.guild.id))

	@commands.has_guild_permissions(manage_guild=True)
	@settings.command()
	async def prefix(self, ctx, new_prefix: str):
		"""Defines a new prefix for the bot"""
		if len(new_prefix) > 5:
			ctx.send('Prefix cannot be longer than 5 characters')
			return
		await db.write("UPDATE guild_prefs SET prefix = ? WHERE guild_id = ?", (new_prefix, ctx.guild.id))

def setup(bot):
    bot.add_cog(Moderation(bot))