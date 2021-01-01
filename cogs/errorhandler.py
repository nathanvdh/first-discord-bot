## Pasted from: https://gist.github.com/EvieePy/7822af90858ef65012ea500bcecf1612

import discord
import traceback
import sys
import checks
import db
from discord.ext import commands

class ErrorHandler(commands.Cog, name='errorhandler'):

	def __init__(self, bot):
		self.bot = bot

	@commands.Cog.listener()
	async def on_command_error(self, ctx, error):
		"""The event triggered when an error is raised while invoking a command.
		Parameters
		------------
		ctx: commands.Context
			The context used for command invocation.
		error: commands.CommandError
			The Exception raised.
		"""
		if hasattr(ctx.command, 'on_error'):
			return

		cog = ctx.cog
		if cog:
			if cog._get_overridden_method(cog.cog_command_error) is not None:
				return

		ignored = (commands.CommandNotFound, )
		error = getattr(error, 'original', error)

		if isinstance(error, ignored):
			return
		
		if isinstance(error, commands.MissingRequiredArgument):
		    await ctx.send_help(ctx.command)	

		if isinstance(error, commands.NotOwner):
			await ctx.send('Only the owner of the bot can use that.')

		if isinstance(error, commands.MissingPermissions):
			perms = '\n'.join(error.missing_perms)
			msg = 'You do not have the following required permissions to do that:\n' + perms
			await ctx.send(msg)
		
		if isinstance(error, commands.DisabledCommand):
			await ctx.send(f'{ctx.command} has been disabled.')

		elif isinstance(error, commands.NoPrivateMessage):
			try:
				await ctx.author.send(f'{ctx.command} can not be used in Private Messages.')
			except discord.HTTPException:
				pass

		elif isinstance(error, checks.NotInBotChannel):
			msg = ('You cannot use commands outside of bot channels, except for !help here in DMs.\n')
			if ctx.guild is None:
				await ctx.author.send(msg)
			else:
				msg += 'The allowed bot channels are:\n'
				bot_channel_ids = ctx.bot.allowed_channels[ctx.guild.id]
				channels_str = ['<#' + str(channel_id) + ">" for channel_id in bot_channel_ids]
				await ctx.author.send(msg.format('\n'.join(channels_str)))
		else:
			print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
			traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

def setup(bot):
	bot.add_cog(ErrorHandler(bot))