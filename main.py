import discord
import logging

import datetime

from functools import partial
from asyncio import TimeoutError
from secret import token
from pickup import start_pickup


logging.basicConfig(level=logging.WARNING)

# intents = discord.Intents.all()


intents = discord.Intents.none()

intents.guilds = True
intents.members = True
intents.voice_states = True
intents.messages = True
intents.reactions = True

bot = discord.Bot(intents=intents)

async def get_player_stats(player_tag):
    url = f"https://quake-stats.bethesda.net/api/v2/Player/Stats?name={player_tag}"
    r = requePsts.get(url)
    player_data = r.content
    return player_data



@bot.listen()
async def on_ready():
    print('We have logged in as {0.user}'.format(bot))
    guilds = bot.guilds
    for guild in guilds:
        print(guild)


async def time_to_next_quake_monday(message):
    today = datetime.date.today()
    if not today.weekday()==0:
        monday = today + datetime.timedelta(days=-today.weekday(), weeks=1)
    else:
        monday = today
    monday = datetime.datetime.fromisoformat(monday.isoformat())
    monday_quake = monday+ datetime.timedelta(hours=19, )
    ts = int(monday_quake.timestamp())
    await message.channel.send(f"<t:{ts}:R>")

@bot.listen('on_message')
async def on_message(ctx):
    if ctx.author.id!=bot.user.id:
        message = await ctx.channel.fetch_message(ctx.id)
    else:
        return 0
    # if starting pug
    if message.content.startswith('$') or message.content.startswith('$pu'):
        await start_pickup(message)
    elif message.content.startswith('$tr'):
        await time_to_next_quake_monday(message)

bot.run(token)
