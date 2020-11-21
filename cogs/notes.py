import discord
from discord.ext import commands

class Notes(commands.Cog):
	"""A notes cog, like many telegram bots have"""
	def __init__(self, bot):
		self.bot = bot
		