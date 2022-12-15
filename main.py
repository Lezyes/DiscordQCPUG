import logging
import discord
import datetime
import redis 
from functools import partial
from asyncio import TimeoutError
from secret import token
from pickup import start_pickup
from pugqueue import queue_up, drop_from_queue, show_queue
from registration import register_player


from discord.ext import commands

db = redis.Redis(host='redis-qc', port=6379, db=0)
#Check existing
for k in ["dcid","qcstats","qcelo"]:
    if not db.exists(k):
        print(f"{k} was missing from the DB!!!????!?!?!?!")
        db.json().set(k, '$', {})
#reset 
for k in ["queue"]:    
    db.json().set(k, '$', {})


intents = discord.Intents.none()
intents.guilds = True
intents.members = True
intents.voice_states = True
intents.messages = True
intents.reactions = True
intents.message_content = True

bot = commands.Bot(command_prefix=commands.when_mentioned_or("$"), intents=intents)


@bot.command()
async def pu(ctx: commands.Context):
    print("pickUP")
    await start_pickup(db=db, message = ctx.message)
    # Setting the reference message to ctx.message makes the bot reply to the member's message.
    # await ctx.send("Tic Tac Toe: X goes first", view=TicTacToe(), reference=ctx.message)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("------")









bot.run(token)
