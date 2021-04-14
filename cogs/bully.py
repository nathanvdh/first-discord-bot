import discord
from discord.ext import commands
import db

class Bully(commands.Cog, name='bully'):
	"""Forces a users nickname"""
	def __init__(self, bot):
		self.bot = bot
		bot.loop.create_task(self.create_table())

	async def create_table(self):
		sql = """CREATE TABLE IF NOT EXISTS forced_nicks(
			user_id integer PRIMARY KEY,
			guild_id integer,
			forced_nick text);"""
		await db.write(sql)

	async def retrieve_nick(self, member: discord.Member):
		sql = """SELECT forced_nick FROM forced_nicks
				WHERE user_id = ?
				AND guild_id = ? ;"""
		vals = (member.id, member.guild.id)
		return await db.fetchfield(sql, vals)

	@commands.Cog.listener()
	async def on_member_update(self, before, after):
		if before.nick == after.nick:
			return
		forced_nick = await self.retrieve_nick(after)
		if forced_nick is not None:
			await after.edit(nick=forced_nick)
		# await after.edit()

	@commands.has_guild_permissions(manage_nicknames=True)
	@commands.command()
	async def bully(self, ctx, member: discord.Member, *, forced_nick):
		if member == self.bot.user or member.guild is None:
			return
		if ctx.message.author.top_role < member.top_role:
			await ctx.send("That member has a bigger discord pp than you. Sorry, you can't bully them.")
			return

		if not await self.retrieve_nick(member):
			sql = """INSERT INTO forced_nicks(user_id, guild_id, forced_nick)
					 VALUES(?, ?, ?);"""
			vals = (member.id, ctx.guild.id, forced_nick)
		else:
			sql = """UPDATE forced_nicks
					 SET forced_nick = ?
					 WHERE user_id = ?
					 AND guild_id = ? ;"""
			vals = (forced_nick, member.id, ctx.guild.id)
		await db.write(sql, vals)

		await member.edit(nick=forced_nick)

	@commands.has_guild_permissions(manage_nicknames=True)
	@commands.command()
	async def unbully(self, ctx, member: discord.Member):
		if not await self.retrieve_nick(member):
			return
		elif ctx.message.author.top_role < member.top_role:
			await ctx.send("That member has a bigger discord pp than you. Sorry, you can't unbully them.")
			return
		else:
			sql = """DELETE FROM forced_nicks
				 WHERE user_id = ?
				 AND guild_id = ? ;"""
			vals = (member.id, ctx.guild.id)
			await db.write(sql, vals)


def setup(bot):
	bot.add_cog(Bully(bot))

		
		