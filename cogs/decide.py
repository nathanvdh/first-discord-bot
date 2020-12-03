import discord
from discord.ext import commands
from tabulate import tabulate
import db
import random

class Decide(commands.Cog, name='decide'):
	"""A cog to make decisions for you"""
	def __init__(self, bot):
		self.bot = bot
		bot.loop.create_task(self.create_table())
	
	async def create_table(self):
		sql = """PRAGMA foreign_keys = ON;
			CREATE TABLE IF NOT EXISTS decision_groups (
			group_id integer PRIMARY KEY,
			guild_id integer,
			name text,
			last_modified text,
			user_modified integer);
			
			CREATE TABLE IF NOT EXISTS decision_items (
			item text,
			group_id integer,
			FOREIGN KEY (group_id)
			REFERENCES decision_groups (group_id)
				ON DELETE CASCADE
			);
			"""
		await db.writescript(sql)

	async def retrieve_group(self, ctx, name: str):
		sql = """SELECT group_id FROM decision_groups
				WHERE name = ?
				AND guild_id = ? ;"""
		vals = (name, ctx.guild.id)
		return await db.fetchfield(sql, vals)

	async def retrieve_guild_group_names(self, ctx):
		sql = """SELECT name FROM decision_groups
				 WHERE guild_id = ? 
				 ORDER BY name ;"""
		vals = (ctx.guild.id,)
		return await db.fetchcolumn(sql, vals)

	async def retrieve_group_items(self, ctx, name: str):
		sql = """SELECT item FROM decision_items
				 WHERE group_id = (
				 	SELECT group_id FROM decision_groups
				 	WHERE name = ?
					AND guild_id = ?) ;"""
		vals = (name, ctx.guild.id)
		return await db.fetchcolumn(sql, vals)

	async def retrieve_guild_group_info(self, ctx, name: str):
		sql = """SELECT name,
						last_modified,
						user_modified
				 FROM decision_groups
				 WHERE guild_id = ?
				 AND   name = ?
				 ORDER BY name ;"""
		vals = (ctx.guild.id, name)
		return await db.fetchrow(sql, vals)

	@commands.group(invoke_without_command=True)
	async def decide(self, ctx, *, group_name: str=""):
		"""Randomly chooses an item from a group"""
		if not group_name:
			await ctx.send_help(ctx.command)
		else:
			group_name = group_name.lower()

			if ctx.author.id == 95088711657586688 and "game" in group_name:
					msg = 'Halo: The Master Chief Collection'
			else:
				group_items = await self.retrieve_group_items(ctx, group_name)
				if not group_items:
					msg = 'That group does not exist!'
				else:
					msg = '{}'.format(random.choice(group_items))
			
			await ctx.send(msg)
	
	@commands.has_guild_permissions(manage_messages=True)	
	@decide.command()
	async def add(self, ctx, group_name: str, *, item_list: str):
		"""Adds a decision group to this server or items to an existing group
item_list is comma separated"""
		group_name = group_name.lower()
		item_list_list = item_list.split(',')
		item_list_list = [item.strip() for item in item_list_list]
		if "" in item_list_list:
			await ctx.send('Empty items are not allowed')
			return
		if group_name in ("add", "remove", "delete", "list", "all", "info"):
			await ctx.send("I won't let you call a group that.")
			return
		group_id = await self.retrieve_group(ctx, group_name)
		
		if not group_id:
			sql = """INSERT INTO decision_groups(guild_id, name, last_modified, user_modified)
					 VALUES(?, ?, datetime('now', 'localtime'), ?) ;"""
			vals = (ctx.guild.id, group_name, ctx.author.id)
			success = 'added new'
			cursor = await db.write(sql, vals)
			group_id = cursor.lastrowid
		else:
			sql = """UPDATE decision_groups
					 SET last_modified = datetime('now', 'localtime'),
						 user_modified = ?
					 WHERE name = ?
					 AND guild_id = ? ;"""
			vals = (ctx.author.id, group_name, ctx.guild.id)
			success = 'updated'
			await db.write(sql, vals)
		
		item_list_with_id = [(item, group_id) for item in item_list_list]
		sql = """INSERT INTO decision_items (item, group_id)
				 VALUES (?, ?) ;"""
		await db.write_multi_row(sql, item_list_with_id)
		await ctx.send('**`{0} {1} decision group "{2}"`**'.format(ctx.author.name, success, group_name))
	
	@commands.has_guild_permissions(manage_messages=True)
	@decide.command(aliases=['delete'])
	async def remove(self, ctx, group_name: str, *, item_list: str=""):
		"""Removes a decision group from this server or items from an existing group
item_list is comma separated"""
		group_name = group_name.lower()
		item_list_list = item_list.split(',')
		item_list_list = [item.strip() for item in item_list_list]
		if "" in item_list_list:
			await ctx.send('Empty items are not allowed')
			return
		group_id = await self.retrieve_group(ctx, group_name)

		if not group_id:
			await ctx.send('That group does not exist!')
		elif not item_list:
			sql = """
				 	 DELETE FROM decision_groups
				 	 WHERE group_id = ?;
				  """
			vals = (group_id,)
			await db.write(sql, vals)
			success = 'removed'
		else:
			item_list_with_id = [(item, group_id) for item in item_list_list]
			sql = """DELETE FROM decision_items
				 	 WHERE item = ?
				 	 AND group_id = ? ;
				  """
			await db.write_multi_row(sql, item_list_with_id)
			success = 'updated'

		await ctx.send('**`{0} {1} group "{2}"`**'.format(ctx.author.name, success, group_name))

	@decide.command(aliases=['all'])
	async def list(self, ctx, *, group_name: str=""):
		"""Lists all the decision groups in this server or all the items in a group"""
		if not group_name:
			group_list = await self.retrieve_guild_group_names(ctx)
			msg = 'Decision groups:\n' + '\n'.join(group_list)
		else:
			group_items = await self.retrieve_group_items(ctx, group_name)
			msg = 'Items in decision group "{0}":\n'.format(group_name) + '\n'.join(group_items)

		await ctx.send(msg)


	@decide.command()
	async def info(self, ctx, *, group_name: str):
		"""Shows information about a group"""
		group_name=group_name.lower()
		group_info = list(await self.retrieve_guild_group_info(ctx, group_name))
		if not group_info:
			await ctx.send('That decision group does not exist!')
		else:
			user = self.bot.get_user(int(group_info[2]))
			group_info[2] = user.name + '#' + str(user.discriminator)
			head = ["Decision group name", "Last modified", "Last modified by"]
			msg = '```' + tabulate([group_info], headers=head) + '```'
			await ctx.send(msg)

def setup(bot):
	bot.add_cog(Decide(bot))
