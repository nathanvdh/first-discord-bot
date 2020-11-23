import discord
from discord.ext import commands
#import aiosqlite
import db
#import asyncio


class Notes(commands.Cog):
	"""A notes cog, like many telegram bots have"""
	def __init__(self, bot):
		self.bot = bot
		bot.loop.create_task(self.create_table())

	async def create_table(self):
		sql = """CREATE TABLE IF NOT EXISTS notes(
			id integer PRIMARY KEY,
			guild_id text NOT NULL,
			name text NOT NULL,
			content text NOT NULL,
			date_added text,
			user_added text);"""
		await db.write(sql)

	@commands.command()
	async def addnote(self, ctx, name: str, *, content: str):
		sql = """INSERT INTO notes(guild_id, name, content, date_added, user_added)
				 VALUES(?, ?, ?, datetime('now'), ?);"""
		vals = (str(ctx.guild.id), name, content, str(ctx.author.id))
		await db.write(sql, vals)

	@commands.command()
	async def note(self, ctx, name: str):
		sql = """SELECT content FROM notes
				 WHERE name = ?
				 AND guild_id = ? ;"""
		vals = (name, str(ctx.guild.id))
		content = await db.fetchone(sql, vals)
		await ctx.send(content)




def setup(bot):
	bot.add_cog(Notes(bot))
