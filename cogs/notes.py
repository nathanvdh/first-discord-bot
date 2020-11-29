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
			guild_id text NOT NULL,
			name text NOT NULL,
			content text NOT NULL,
			date_added text,
			user_added text);"""
		await db.write(sql)

	async def retrieve_note(self, ctx, name: str):
		sql = """SELECT content FROM notes
			 	WHERE name = ?
			 	AND guild_id = ? ;"""
		vals = (name, str(ctx.guild.id))
		return await db.fetchone(sql, vals)

	async def retrieve_guild_note_names(self, ctx):
		sql = """SELECT name FROM notes
				 WHERE guild_id = ? 
				 ORDER BY name ;"""
		vals = (str(ctx.guild.id),)
		return await db.fetchall(sql, vals)

	async def retrieve_guild_note_infos(self, ctx, name: str):
		sql = """SELECT name,
						date_added,
						user_added
				 FROM notes
				 WHERE guild_id = ?
				 AND   name = ?
				 ORDER BY name ;"""
		vals = (str(ctx.guild.id), name)
		note_infos = await db.fetchall(sql, vals)
		if note_infos:
			note_infos = list(note_infos[0])
		return note_infos

	@commands.group(invoke_without_command=True)
	async def note(self, ctx, note_name: str=""):
		"""Retrieves a note"""
		if not note_name:
			await ctx.send_help(ctx.command)
		else:
			content = await self.retrieve_note(ctx, note_name)
			if content is None:
				await ctx.send('That note does not exist!')
			else:
				await ctx.send(content)
	
	@note.command()
	async def add(self, ctx, name: str, *, content: str):
		"""Adds a note to this server"""
		if name in ("add", "remove", "list", "info", "all"):
			await ctx.send("I won't let you do that")
			return

		if await self.retrieve_note(ctx, name) is None:
			sql = """INSERT INTO notes(guild_id, name, content, date_added, user_added)
				 	 VALUES(?, ?, ?, datetime('now'), ?);"""
			vals = (str(ctx.guild.id), name, content, str(ctx.author.id))
			success = 'added new'
		else:
			sql = """UPDATE notes
					 SET content = ?,
					 	 date_added = datetime('now'),
					 	 user_added = ?
					 WHERE name = ?
					 AND guild_id = ? ;"""
			vals = (content, str(ctx.author.id), name, str(ctx.guild.id))
			success = 'updated'
		await db.write(sql, vals)
		await ctx.send('**`{0} {1} note "{2}"`**'.format(ctx.author.name, success, name))

	@note.command(aliases=['delete'])
	async def remove(self, ctx, name: str):
		"""Removes a note from this server"""
		if not await self.retrieve_note(ctx, name):
			await ctx.send('That note does not exist!')
		else:
			sql = """DELETE FROM notes
				 WHERE name = ?
				 AND guild_id = ? ;"""
			vals = (name, str(ctx.guild.id))
			await db.write(sql, vals)
			await ctx.send('**`Deleted note "{}"`**'.format(name))

	@note.command(aliases=['all'])
	async def list(self, ctx):
		"""Lists all the notes in this server"""
		note_list = await self.retrieve_guild_note_names(ctx)
		msg = 'Notes:\n' + '\n'.join(tup[0] for tup in note_list)
		await ctx.send(msg)

	@note.command()
	async def info(self, ctx, note_name: str):
		"""Shows information about a note"""
		note_infos = await self.retrieve_guild_note_infos(ctx, note_name)
		if not note_infos:
			await ctx.send('That note does not exist!')
		else:
			user = self.bot.get_user(int(note_infos[2]))
			note_infos[2] = user.name + '#' + str(user.discriminator)
			head = ["Note name", "Added on", "Added by"]
			msg = '```' + tabulate([note_infos], headers=head) + '```'
			await ctx.send(msg)

def setup(bot):
	bot.add_cog(Notes(bot))
