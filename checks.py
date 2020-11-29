import discord
from discord.ext import commands
from discord.utils import get
import db

class NotInBotChannel(commands.CheckFailure):
    pass

async def get_bot_channels_string_list(guild_id):
    bot_channel_ids = await db.fetchone("SELECT bot_channels FROM guild_prefs WHERE guild_id = ? ;", (guild_id,))
    if not bot_channel_ids:
        return bot_channel_ids
    else:
        return list(filter(None,bot_channel_ids.split(',')))

async def bot_channel_only(ctx):
    if ctx.guild is None:
    	if ctx.invoked_with == "help":
    		return True
    
    bot_channel_ids = await get_bot_channels_string_list(ctx.guild.id)
    if not bot_channel_ids:
        return True
    bot_channel_ids_list_ints = [int(x) for x in bot_channel_ids]
    if ctx.channel in [ctx.bot.get_channel(id) for id in bot_channel_ids_list_ints]:
        return True
    raise NotInBotChannel()