import discord
from discord.ext import commands

class Dad(commands.Cog, name='dad'):
	"""Hi ___, I'm dad"""
	def __init__(self, bot):
		self.bot = bot
		self.im = ("I\'m", "i\'m", "Im", "im")
	
	@commands.Cog.listener()
	async def on_message(self, message):
		if message.author == self.bot.user or message.guild is None:
			return
		msg = message.content
		for prefix in self.im:
			if msg.startswith(prefix+" "):
				msg = msg[len(prefix)+1:]
				await message.channel.send('Hi {0}, I\'m {1.user.name}'.format(msg, self.bot))
				break


def setup(bot):
	bot.add_cog(Dad(bot))

		
		