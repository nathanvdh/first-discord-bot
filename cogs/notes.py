import discord
from discord.ext import commands
from tabulate import tabulate
import db

class Notes(commands.Cog, name='notes'):
	"""A notes cog, like many telegram bots have"""
	def __init__(self, bot):
		self.bot = bot
		bot.loop.create_task(self.create_table())

	async def create_table(self):
		sql = """CREATE TABLE IF NOT EXISTS notes(
			id integer PRIMARY KEY,
			guild_id integer,
			name text,
			content text,
			date_added text,
			user_added integer);"""
		await db.write(sql)

	async def retrieve_note(self, ctx, name: str):
		sql = """SELECT content FROM notes
				WHERE name = ?
				AND guild_id = ? ;"""
		vals = (name, ctx.guild.id)
		return await db.fetchfield(sql, vals)

	async def retrieve_guild_note_names(self, ctx):
		sql = """SELECT name FROM notes
				 WHERE guild_id = ? 
				 ORDER BY name ;"""
		vals = (ctx.guild.id,)
		return await db.fetchcolumn(sql, vals)

	async def retrieve_guild_note_info(self, ctx, name: str):
		sql = """SELECT name,
						date_added,
						user_added
				 FROM notes
				 WHERE guild_id = ?
				 AND   name = ? ;"""
		vals = (ctx.guild.id, name)
		note_info = await db.fetchrow(sql, vals)
		return note_info

	@commands.group(invoke_without_command=True)
	async def note(self, ctx, *, note_name: str=""):
		"""Retrieves a note"""
		if not note_name:
			await ctx.send_help(ctx.command)
		else:
			note_name = note_name.lower()
			content = await self.retrieve_note(ctx, note_name)
			if content is None:
				await ctx.send('That note does not exist!')
			else:
				await ctx.send(content, allowed_mentions=discord.AllowedMentions.none())
	
	@commands.has_guild_permissions(manage_messages=True)
	@note.command()
	async def add(self, ctx, note_name: str, *, content: str):
		"""Adds a note to this server"""
		note_name = note_name.lower()
		if note_name in ("add", "delete", "remove", "list", "all", "info"):
			await ctx.send("I won't let you do that.")
			return

		if await self.retrieve_note(ctx, note_name) is None:
			sql = """INSERT INTO notes(guild_id, name, content, date_added, user_added)
					 VALUES(?, ?, ?, datetime('now', 'localtime'), ?);"""
			vals = (ctx.guild.id, note_name, content, ctx.author.id)
			success = 'added new'
		else:
			sql = """UPDATE notes
					 SET content = ?,
						 date_added = datetime('now', 'localtime'),
						 user_added = ?
					 WHERE name = ?
					 AND guild_id = ? ;"""
			vals = (content, ctx.author.id, note_name, ctx.guild.id)
			success = 'updated'
		await db.write(sql, vals)
		await ctx.send('**`{0} {1} note "{2}"`**'.format(ctx.author.name, success, note_name))
	
	@commands.has_guild_permissions(manage_messages=True)
	@note.command(aliases=['delete'])
	async def remove(self, ctx, note_name: str):
		"""Removes a note from this server"""
		note_name = note_name.lower()
		if not await self.retrieve_note(ctx, note_name):
			await ctx.send('That note does not exist!')
		else:
			sql = """DELETE FROM notes
				 WHERE name = ?
				 AND guild_id = ? ;"""
			vals = (note_name, ctx.guild.id)
			await db.write(sql, vals)
			await ctx.send('**`Deleted note "{}"`**'.format(note_name))

	@note.command(aliases=['all'])
	async def list(self, ctx):
		"""Lists all the notes in this server"""
		note_list = await self.retrieve_guild_note_names(ctx)
		msg = 'Notes:\n' + '\n'.join(note_list)
		await ctx.send(msg)

	@note.command()
	async def info(self, ctx, note_name: str):
		"""Shows information about a note"""
		note_name=note_name.lower()
		note_info = list(await self.retrieve_guild_note_info(ctx, note_name))
		if not note_info:
			await ctx.send('That note does not exist!')
		else:
			user = self.bot.get_user(note_info[2])
			note_info[2] = user.name + '#' + str(user.discriminator)
			head = ["Note name", "Added on", "Added by"]
			msg = '```' + tabulate([note_info], headers=head) + '```'
			await ctx.send(msg)

def setup(bot):
	bot.add_cog(Notes(bot))
