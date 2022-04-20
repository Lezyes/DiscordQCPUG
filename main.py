import discord
import logging
from secret import token
from guild_games_roles import guilds_roles
from text_to_emojis import emoji_dict
from functools import partial
from random import randint
from asyncio import TimeoutError
import datetime




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

def shuffle_list(l):
    for i in range(len(l) * 2):
        r = randint(0, len(l) - 1)
        l.append(l.pop(r))
    return l[0::2], l[1::2]


@bot.listen()
async def on_ready():
    print('We have logged in as {0.user}'.format(bot))
    guilds = bot.guilds
    for guild in guilds:
        print(guild)

class AddPlayersModal(discord.ui.Modal):
    def __init__(self, data_dict, original_view, original_interaction, *args, **kwargs) -> None:
        self.data_dict = data_dict
        self.original_view = original_view
        self.current_stage = data_dict["current_stage"]
        self.original_interaction = original_interaction
        super().__init__(title = "Add Players Manually",*args, **kwargs)
        for i in range(5):
            self.add_item(discord.ui.InputText(label="Player Name",
                                               required = False))

    async def callback(self, interaction: discord.Interaction):
        embed = discord.Embed(title="Your Modal Results", color=discord.Color.random())
        data_dict = self.data_dict
        original_interaction = self.original_interaction
        players = set()
        for child in self.children:
            if child.value:
                players.add(child.value)
        
        new_players = players.difference(data_dict["players"])
        data_dict["players"] = data_dict["players"].union(new_players)
        data_dict["selections"][self.current_stage] = new_players.union([child_interface.label for 
                                                          child_interface in self.original_view.children
                                                          if isinstance(child_interface, discord.ui.Button)
                                                          and child_interface.style==discord.ButtonStyle.primary])
        msg = self.original_interaction.message
        await msg.delete()
        await pick_players(data_dict)
        await interaction.response.send_message(embeds=[embed], delete_after = 0)




class SelectionGenericButton(discord.ui.Button):
    def __init__(self, data_dict, callback_func, label=None, style = None):
        if not style:
            style = discord.ButtonStyle.success
        if not label:
            label = "Button"
        self.data_dict = data_dict
        self.current_stage = data_dict["current_stage"]
        self.callback_func = callback_func
        super().__init__(
            label=label,
            style=style,
        )
    async def callback(self, interaction):
        await self.callback_func(self, interaction, self.data_dict)

class Dropdown(discord.ui.Select):
    def __init__(self, options, title="Pick your pick"):
        self.options_data = options
        select_options = [
            discord.SelectOption(label=option) for option in options
        ]
        super().__init__(
            placeholder=title,
            min_values=1,
            max_values=len(options),
            options=select_options,
        )

class SelectView(discord.ui.View):
    def __init__(self, data_dict):
        super().__init__()
        # Adds the dropdown to our view object.
        selection_options = data_dict["dropdowns"].get(data_dict["current_stage"],{})
        ol = list(selection_options.keys())
        for sub_list in [ol[i * 5:(i + 1) * 5] for i in range(len(ol) // 5 + 1)]:
            if sub_list:
                sub_dict = {k: selection_options[k] for k in sub_list}
                self.add_item(Dropdown(sub_dict))

        for button in data_dict["buttons"].get(data_dict["current_stage"], []):
            self.add_item(SelectionGenericButton(data_dict=data_dict, 
                                                 **button))


async def button_pressed(self, interaction, data_dict):
    self.style = discord.ButtonStyle.secondary if self.style==discord.ButtonStyle.primary else discord.ButtonStyle.primary
    msg = interaction.message
    await msg.edit(view = self.view)

async def buttons_all(self, interaction, data_dict):
    for child_interface in self.view.children:
        if isinstance(child_interface, discord.ui.Button) and child_interface.style==discord.ButtonStyle.secondary:
            child_interface.style = discord.ButtonStyle.primary
    msg = interaction.message
    await msg.edit(view = self.view)

async def selection_all(self, interaction, data_dict):
    for child_interface in self.view.children:
        if isinstance(child_interface, discord.ui.Select):
            for option in child_interface.options:
                option.default = True
                child_interface.values.append(option.value)
    msg = interaction.message
    await msg.edit(view = self.view)

async def collect_buttons_finish(self, interaction, data_dict):
    items = self.view.children
    data_dict["selections"][self.current_stage] = {child_interface.label for child_interface in self.view.children if isinstance(child_interface, discord.ui.Button) and child_interface.style == discord.ButtonStyle.primary}
    await data_dict["flow"][self.current_stage](data_dict)

async def collect_selection_finish(self, interaction, data_dict):
    items = self.view.children
    data_dict["selections"][self.current_stage] = {val: child_interface.options_data[val] for child_interface in items if isinstance(child_interface, discord.ui.Select) for val in child_interface.values}
    await data_dict["flow"][self.current_stage](data_dict)

async def add_players_manually(self, interaction, data_dict):
    items = self.view.children
    await interaction.response.send_modal(AddPlayersModal(data_dict, 
                                                          original_view = self.view, 
                                                          original_interaction = interaction))
    

    # msg = interaction.message
    # await msg.edit(view = self.view)


async def players_source(data_dict):
    current_stage = "players_source"
    data_dict["current_stage"] = current_stage
    data_dict["buttons"].setdefault(current_stage, [])
    data_dict["buttons"][current_stage].append({
                                "callback_func":selection_all,
                                "label":"Select All",
                                "style":discord.ButtonStyle.primary})
    data_dict["buttons"][current_stage].append({
                                "callback_func":collect_selection_finish,
                                "label":"Continue With Current Selection",
                                "style":discord.ButtonStyle.success})
    return await data_dict["thread"].send("Choose a Source!", view=SelectView(data_dict))

def players_from_selection(data_dict):
    return data_dict.get("players", set()).union({m.display_name for v in data_dict["selections"]["players_source"].values() for m in v.members})

async def pick_players(data_dict):
    data_dict["players"] = players_from_selection(data_dict)
    current_stage = "pick_players"
    data_dict["current_stage"] = current_stage

    data_dict["buttons"][current_stage] = [{"callback_func":button_pressed,
                                    "label":player,
                                    "style":discord.ButtonStyle.primary 
                                            if player in data_dict["selections"].get(current_stage, set())
                                            else discord.ButtonStyle.secondary 
                                    }
                                    for player in sorted(data_dict["players"])
                                    ]

    util_buttons = [{"callback_func":buttons_all,
                    "label":"Select All",
                    "style":discord.ButtonStyle.danger},
                    {"callback_func":add_players_manually,
                    "label":"Add Players Manually",
                    "style":discord.ButtonStyle.danger},
                    {"callback_func":collect_buttons_finish,
                    "label":"Continue With Current Selection",
                    "style":discord.ButtonStyle.success}
                    ]
    for button in util_buttons:
        # if button["label"] not in [b["label"] for b in data_dict["buttons"][current_stage]]:
        data_dict["buttons"][current_stage].append(button)
    return await data_dict["thread"].send("Pick Players!", view=SelectView(data_dict))
  

async def choose_balance_func(data_dict):
    current_stage = "choose_balance_func"
    data_dict["current_stage"] = "choose_balance_func"
    players = data_dict["selections"]["pick_players"]
    if len(data_dict["team_balance_options"]) > 1:
        pass
    else:
        data_dict["balance_func"] = list(data_dict["team_balance_options"].values())[0]
        await data_dict["flow"][current_stage](data_dict)

async def assign_players(data_dict):
    current_stage = "assign_players"
    players = data_dict["selections"]["pick_players"]

    balance_func = data_dict["balance_func"]
    team1, team2 = balance_func(list(players))

    team1 = ", ".join(team1)
    team2 = ", ".join(team2)
    text = f"Team 1:{team1}\nTeam 2:{team2} "
    await data_dict["channel"].send(text)
    await data_dict["thread"].delete()
    await data_dict["message"].delete()

@bot.listen('on_message')
async def on_message(ctx):
    if ctx.author.id!=bot.user.id:
        message = await ctx.channel.fetch_message(ctx.id)
    else:
        return 0
    # if starting pug
    if message.content.startswith('$pickup') or message.content.startswith('$pu'):
        thread = await message.create_thread(name="Pickup Organizer", auto_archive_duration=60)
        team_balance_options = {"Random": shuffle_list}
        author = message.author
        guild = message.guild
        channel = message.channel
        roles = guilds_roles.get(guild.id, {}).get("roles")
        channels = guilds_roles.get(guild.id, {}).get("channels")
        data_dict = {
            "team_balance_options": team_balance_options,
            "message": message,
            "thread": thread,
            "author": author,
            "guild": guild,
            "channel": channel,
            "roles": roles,
            "channels": channels,
            "selected_players":set(),
            "players": set(),
            "selections":{},
            "dropdowns":{},
            "buttons": {},
        }
        # get players from channels
        sources = {}
        for role in guild.roles:
            if role.id in roles:
                sources[role.name] = role
        for guild_channel in guild.channels:
            if guild_channel.id in channels:
                sources[guild_channel.name] = guild_channel
        data_dict["flow"] = {"players_source": pick_players,
                             "pick_players": choose_balance_func,
                             "choose_balance_func":assign_players}
        data_dict["dropdowns"]["players_source"] = sources

        await players_source(data_dict)

    elif message.content.startswith('$tr'):
        today = datetime.date.today()
        if not today.weekday()==0:
            monday = today + datetime.timedelta(days=-today.weekday(), weeks=1)
        else:
            monday = today
        monday = datetime.datetime.fromisoformat(monday.isoformat())
        monday_quake = monday+ datetime.timedelta(hours=19, )
        ts = int(monday_quake.timestamp())
        await message.channel.send(f"<t:{ts}:R>")


bot.run(token)
