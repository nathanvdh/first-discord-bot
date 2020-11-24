## Pasted from: https://gist.github.com/EvieePy/d78c061a4798ae81be9825468fe146be#file-owner-py

from discord.ext import commands
from discord.utils import get
import checks
class BotConfig(commands.Cog, command_attrs=dict(hidden=True)):
	"""Cog for configuring the bot from within discord"""
	def __init__(self, bot):
		self.bot = bot
		self.hidden = True
			
	async def cog_check(self, ctx):
		"""Check if user has admin role"""
		return checks.is_admin(ctx)

	@commands.command(name='load')
	async def load_cog(self, ctx, *, cog: str):
		"""Loads an extension"""
		try:
			self.bot.load_extension("cogs."+cog)
		except Exception as e:
			await ctx.send(f'**`ERROR:`** {type(e).__name__} - {e}')
		else:
			await ctx.send('**`SUCCESS`**')
	@commands.command(name='unload')
	async def unload_cog(self, ctx, *, cog: str):
		"""Unloads an extension"""
		try:
			self.bot.unload_extension("cogs."+cog)
		except Exception as e:
			await ctx.send(f'**`ERROR:`** {type(e).__name__} - {e}')
		else:
			await ctx.send('**`SUCCESS`**')
	@commands.command(name='reload')
	async def reload_cog(self, ctx, *, cog: str):
		"""Reloads an extension"""
		try:
			self.bot.unload_extension("cogs."+cog)
			self.bot.load_extension("cogs."+cog)
		except Exception as e:
			await ctx.send(f'**`ERROR:`** {type(e).__name__} - {e}')
		else:
			await ctx.send('**`SUCCESS`**')
def setup(bot):
	bot.add_cog(BotConfig(bot))