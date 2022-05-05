import discord
import logging

import datetime
import redis 
from functools import partial
from asyncio import TimeoutError
from secret import token
from pickup import start_pickup
from pugqueue import queue_up, drop_from_queue, show_queue
from registration import register_player

db = redis.Redis(host='localhost', port=6379, db=0)
#Check existing
for k in ["dcid","qcstats","qcelo"]:
    if not db.exists(k):
        print(f"{k} was missing from the DB!!!????!?!?!?!")
        db.json().set(k, '$', {})
#reset 
for k in ["queue"]:    
    db.json().set(k, '$', {})

logging.basicConfig(level=logging.WARNING)

# intents = discord.Intents.all()
intents = discord.Intents.none()
intents.guilds = True
intents.members = True
intents.voice_states = True
intents.messages = True
intents.reactions = True

bot = discord.Bot(intents=intents)

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
    await message.delete()


async def help_msg(message, command_dict):
    help_dict = {}
    for cmd,d in command_dict.items():
        help_dict.setdefault(d["description"], [])
        help_dict[d["description"]].append(cmd)
    text = "You can interact with the bot by sending the following commands:\n"
    for desc,cmds in help_dict.items():
        text += "`{}`: {}\n".format("`,`".join(cmds), desc)

    await message.channel.send(text)
    await message.delete()


@bot.listen('on_message')
async def on_message(ctx):
    if ctx.author.id!=bot.user.id:
        message = await ctx.channel.fetch_message(ctx.id)
    else:
        return 0
    # if starting pug
    command_dict = {
                "$pickup":{"func":partial(start_pickup, db=db), "description":"Start a Pickup"},
                "$pu":{"func":partial(start_pickup, db=db), "description":"Start a Pickup"},
                "$tr":{"func":time_to_next_quake_monday, "description":"Post how much time untill next monday quake night"},
                "$reg":{"func":partial(register_player, db = db), "description":"Register quake name"},
                "$register":{"func":partial(register_player, db = db), "description":"Register quake name"},
                "$queue":{"func":partial(queue_up, db = db), "description":"Queue up for a PUG"},
                "$qu":{"func":partial(queue_up, db = db), "description":"Queue up for a PUG"},
                "$drop":{"func":partial(drop_from_queue, db = db), "description":"Drop from queue"},
                "$dq":{"func":partial(drop_from_queue, db = db), "description":"Drop from queue"},
                "$qs":{"func":partial(show_queue, db = db), "description":"Show existing queues status"},
                "$help": {"description":"Print all bot commands"},
                }
    command_dict["$help"]["func"] = partial(help_msg, command_dict = command_dict)

    return [await cmd["func"](message) for option,cmd in command_dict.items() if message.content.startswith(option)]
    
bot.run(token)
