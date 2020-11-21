import discord
from discord.ext import commands

class Dad(commands.Cog):
	"""A notes cog, like many telegram bots have"""
	def __init__(self, bot):
		self.bot = bot
		self.im = ("I\'m", "i\'m", "Im", "im")
	
	@commands.Cog.listener()
	async def on_message(self, message):
		msg = message.content
		
		for prefix in self.im:
			if msg.startswith(prefix+" "):
				msg = msg[len(prefix)+1:]
				await message.channel.send('Hi {0}, I\'m {1.user.name}'.format(msg, self.bot))
				break


def setup(bot):
	bot.add_cog(Dad(bot))

		
		