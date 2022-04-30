import discord
from botui import SelectView, selection_all, collect_selection_finish, button_pressed, buttons_all, collect_buttons_finish
from guild_games_roles import guilds_roles
from random import randint
import json
import requests

def shuffle_list(l):
    for i in range(len(l) * 2):
        r = randint(0, len(l) - 1)
        l.append(l.pop(r))
    return l[0::2], l[1::2]

async def get_player_stats(player_tag):
    url = f"https://quake-stats.bethesda.net/api/v2/Player/Stats?name={player_tag}"
    r = requests.get(url)
    player_data = r.json()
    return player_data

class InputModal(discord.ui.Modal):
    def __init__(self, data_dict, original_view, original_interaction, callback_func, input_fields = 5,*args, **kwargs) -> None:
        self.data_dict = data_dict
        self.original_view = original_view
        self.current_stage = data_dict["current_stage"]
        self.original_interaction = original_interaction
        self.callback_func = callback_func
        super().__init__(title = "Add Players Manually",*args, **kwargs)
        for i in range(min(5,input_fields)):
            self.add_item(discord.ui.InputText(label="Player Name",
                                               required = False))

    async def callback(self, interaction: discord.Interaction):
        await self.callback_func(self, interaction)


async def get_player_name_input_callback(self, interaction: discord.Interaction):
    embed = discord.Embed(title="Your Modal Results", color=discord.Color.random())
    data_dict = self.data_dict
    player_name = self.children[0].value
    data_dict["player_data"]["quake_name"] = player_name
    jdb = data_dict["db"].json()
    jdb.set("dcid", ".{}.quake_name".format(data_dict["author"].id), player_name)
    await refresh_player_data(data_dict, self.original_interaction)
    await interaction.response.send_message(embeds=[embed], delete_after = 0)    

async def add_players_manually_input_callback(self, interaction: discord.Interaction):
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

async def add_players_manually(self, interaction, data_dict):
    return await interaction.response.send_modal(InputModal(data_dict,
                                                          original_view=self.view,
                                                          original_interaction=interaction,
                                                          callback_func=add_players_manually_input_callback,
                                                          ))


async def players_source(data_dict):
    current_stage = "players_source"
    data_dict["current_stage"] = current_stage
    data_dict["buttons"].setdefault(current_stage, [])
    data_dict["buttons"][current_stage].append({
        "callback_func": selection_all,
        "label": "Select All",
        "style": discord.ButtonStyle.primary})
    data_dict["buttons"][current_stage].append({
        "callback_func": collect_selection_finish,
        "label": "Continue With Current Selection",
        "style": discord.ButtonStyle.success})
    return await data_dict["thread"].send("Choose a Source!", view=SelectView(data_dict))


def players_from_selection(data_dict):
    return data_dict.get("players", set()).union({m.display_name for v in data_dict["selections"]["players_source"].values() for m in v.members})


async def pick_players(data_dict):
    data_dict["players"] = players_from_selection(data_dict)
    current_stage = "pick_players"
    data_dict["current_stage"] = current_stage

    data_dict["buttons"][current_stage] = [{"callback_func": button_pressed,
                                            "label": player,
                                            "style": discord.ButtonStyle.primary
                                            if player in data_dict["selections"].get(current_stage, set())
                                            else discord.ButtonStyle.secondary
                                            }
                                           for player in sorted(data_dict["players"])
                                           ]

    util_buttons = [{"callback_func": buttons_all,
                     "label": "Select All",
                     "style": discord.ButtonStyle.danger},
                    {"callback_func": add_players_manually,
                     "label": "Add Players Manually",
                     "style": discord.ButtonStyle.danger},
                    {"callback_func": collect_buttons_finish,
                     "label": "Continue With Current Selection",
                     "style": discord.ButtonStyle.success}
                    ]
    for button in util_buttons:
        data_dict["buttons"][current_stage].append(button)
    return await data_dict["thread"].send("Pick Players!", view=SelectView(data_dict))


async def choose_balance_func(data_dict):
    current_stage = "choose_balance_func"
    data_dict["current_stage"] = "choose_balance_func"
    players = data_dict["selections"]["pick_players"]
    if len(data_dict["team_balance_options"]) > 1:
        pass
    else:
        data_dict["balance_func"] = list(
            data_dict["team_balance_options"].values())[0]
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
    # await data_dict["thread"].delete()
    await data_dict["message"].delete()


async def start_pickup(message):
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
        "selected_players": set(),
        "players": set(),
        "selections": {},
        "dropdowns": {},
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
                         "choose_balance_func": assign_players}
    data_dict["dropdowns"]["players_source"] = sources

    await players_source(data_dict)


async def calc_elos(data_dict):
    db = data_dict["db"]







    db.save()
    

async def refresh_player_data(data_dict, interaction = None):
    if data_dict.get("player_data",{}).get("quake_name"):
        quake_name = data_dict["player_data"]["quake_name"]
    else:
        return await data_dict["thread"].send("Error: DB entry for user id `{}` is missing your Quake name, please register first".format(data_dict["author"].id))
    player_stats = await get_player_stats(quake_name)
    if player_stats.get("code")==404:
        return await data_dict["thread"].send("Error: 404 `{}` is resulting in a 404 from quake-stats api".format(quake_name))
    data_dict["qcstats"] = player_stats
    
    db = data_dict["db"]
    jdb = db.json()
    
    jdb.set("qcstats", ".{}".format(quake_name), player_stats)

    await calc_elos(data_dict)
    if data_dict["clean_up"]:
        await data_dict["message"].delete()
    else:
        await data_dict["message"].reply("Successfully updated DB entry with quake-stats data")
    if interaction:
        await interaction.message.delete()

async def register_new_player(self, interaction, data_dict):
    return await interaction.response.send_modal(InputModal(data_dict,
                                                          original_view=self.view,
                                                          original_interaction=interaction,
                                                          callback_func=get_player_name_input_callback,
                                                          input_fields=1
                                                          ))

async def show_player_stats(data_dict):
    pass

async def register_player(message, db):
    current_stage = "db_options"
    if message.guild:
        thread = await message.create_thread(name="Register", auto_archive_duration=60)
        clean_up = True
    else:
        thread = message.channel
        clean_up = False
    author = message.author
    channel = message.channel
    
    data_dict = {
        "current_stage":current_stage,
        "clean_up": clean_up,
        "message": message,
        "thread": thread,
        "author": author,
        "channel": channel,
        "db":db,
        "selections": {},
        "dropdowns": {},
        "buttons": {current_stage:[]},
        "player_data":{}
    }
    
    jdb = db.json()
    player_data = jdb.get("dcid", "$.{}".format(author.id))
    if player_data:
        data_dict["player_data"] = player_data[0]
        data_dict["buttons"][current_stage].append({
                                                "callback_func": lambda self, interaction, data_dict:refresh_player_data(data_dict, interaction),
                                                "label": "Refresh stats",
                                                "style": discord.ButtonStyle.primary
                                                }
                                              )
    else:
        jdb.set("dcid", ".{}".format(author.id), {})
    data_dict["buttons"][current_stage].append({"callback_func":register_new_player,
                                                "label": "Register Quake Name",
                                                "style": discord.ButtonStyle.primary
                                                }
                                              )
    data_dict["buttons"][current_stage].append({"callback_func": lambda self, interaction, data_dict:show_player_stats(data_dict),
                                                "label": "See Stats",
                                                "style": discord.ButtonStyle.primary
                                                }
                                              )
    return await thread.send("What would you like to do?", view=SelectView(data_dict))
