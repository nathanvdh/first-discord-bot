## Pasted from: https://gist.github.com/EvieePy/d78c061a4798ae81be9825468fe146be#file-owner-py

from discord.ext import commands
from discord.utils import get
import checks
class BotConfig(commands.Cog, name='botconfig'):#, command_attrs=dict(hidden=True)):
	"""Cog for configuring the bot from within discord"""
	def __init__(self, bot):
		self.bot = bot
		self.hidden = True
			
	async def cog_check(self, ctx):
		"""Check if user has admin role"""
		return await self.bot.is_owner(ctx.author)

	async def cog_command_error(self, ctx, error):
		if hasattr(ctx.command, 'on_error'):
			return
		if isinstance(error, commands.MissingRequiredArgument):
			await ctx.send_help(ctx.command)
		else:
			await ctx.send(f'**`ERROR:`** {type(error).__name__} - {error}')

	@commands.group()
	async def cog(self, ctx):
		"""Manage cogs"""
		if ctx.invoked_subcommand is None:
			await ctx.send_help(ctx.command)

	@cog.command(name='load')
	async def load_cog(self, ctx, *, cog: str):
		"""Loads a cog"""
		self.bot.load_extension("cogs."+cog)
		await ctx.send('**`Successfully loaded {}`**'.format(cog))
	
	@cog.command(name='unload')
	async def unload_cog(self, ctx, *, cog: str):
		"""Unloads a cog"""
		self.bot.unload_extension("cogs."+cog)
		await ctx.send('**`Successfully unloaded {}`**'.format(cog))	
	
	@cog.command(name='reload')
	async def reload_cog(self, ctx, *, cog: str):
		"""Reloads a cog"""
		self.bot.unload_extension("cogs."+cog)
		self.bot.load_extension("cogs."+cog)
		await ctx.send('**`Successfully reloaded {}`**'.format(cog))

	@commands.command()
	async def shutdown(self, ctx):
		await self.bot.logout()

	@commands.command()
	async def rename(self, ctx, *, name: str):
		await self.bot.user.edit(username=name)
		await ctx.send('**`Renamed bot to {}`**'.format(name))

def setup(bot):
	bot.add_cog(BotConfig(bot))