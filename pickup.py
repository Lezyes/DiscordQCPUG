import discord
from botui import SelectView, selection_all, collect_selection_finish, button_pressed, buttons_all, collect_buttons_finish
from guild_games_roles import guilds_roles
from random import randint
import json
import requests
from itertools import combinations
from functools import partial


async def jdb_get(jdb, key, path = None):
    if path:
        return jdb.get(key, path)
    else:
        return jdb.get(key)

async def jdb_set(jdb, key, value, path = None):
    if path:
        return jdb.set(key, path, value)
    else:
        return jdb.set(key, "$", value)

async def shuffle_list(players_elo):
    l = list(players_elo.keys())
    for i in range(len(l) * 2):
        r = randint(0, len(l) - 1)
        l.append(l.pop(r))
    return [(l[0::2], l[1::2])]

async def pick_from_top(players_elo):
    soreted_by_elo = sorted(players_elo.items(), key=lambda x:x[1], reverse=True)
    team1_elos = soreted_by_elo[0::2] 
    team2_elos = soreted_by_elo[1::2]
    team1 = [p[0] for p in team1_elos]
    team1.append("Total ELO: {}".format(sum([p[1] for p in team1_elos])))
    team2 = [p[0] for p in team2_elos]
    team2.append("Total ELO: {}".format(sum([p[1] for p in team2_elos])))
    return [(team1, team2)]

async def weighted_player_allocation(players_elo):
    soreted_by_elo = sorted(players_elo.items(), key=lambda x:x[1], reverse=True)
    elo_sum = sum(players_elo.values())
    team1_options = sorted([(comb, abs(elo_sum/2-sum((player[1] for player in comb)))) 
                             for comb in combinations(soreted_by_elo, len(players_elo)//2) 
                             if soreted_by_elo[0] in comb],
                           key=lambda x:x[1])
    top3_teams = team1_options[:3]
    teams = []
    for team1_option in top3_teams:
        team1_elo = {p[0]:players_elo[p[0]] for p in team1_option[0]}
        team2_elo = {p:v for p,v in players_elo.items() if p not in team1_elo}
        team1 = list(team1_elo.keys())
        team2 = list(team2_elo.keys())
        team1.append("Total ELO: {}".format(sum([v for v in team1_elo.values()])))
        team2.append("Total ELO: {}".format(sum([v for v in team2_elo.values()])))
        teams.append((team1,team2))
    return teams

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


async def get_player_name_input_callback(self, interaction: discord.Interaction, register = False):
    embed = discord.Embed(title="Getting Player's Data, Please Wait", color=discord.Color.random())
    await interaction.response.send_message(embeds=[embed], delete_after = 0)    
    data_dict = self.data_dict
    clean_up = data_dict["clean_up"]
    data_dict["clean_up"] = False
    for child in self.children:
        player_name = child.value.lower()
        if player_name:

            data_dict["player_data"]["quake_name"] = player_name
            jdb = data_dict["db"].json()
            if register:
                jdb.set("dcid", ".{}.quake_name".format(data_dict["author"].id), player_name)

            await refresh_player_data(data_dict, self.original_interaction)
    data_dict["clean_up"] = clean_up
    if data_dict["clean_up"]:
        await clean_up_msg(data_dict)

async def add_players_manually_input_callback(self, interaction: discord.Interaction):
    embed = discord.Embed(title="Adding Players To Game, Please Wait", color=discord.Color.random())
    await interaction.response.send_message(embeds=[embed], delete_after = 0)
    data_dict = self.data_dict
    original_interaction = self.original_interaction
    players = set()
    for child in self.children:
        if child.value:
            players.add(child.value.lower())
    
    new_players = players.difference(data_dict["players"])
    data_dict["players"] = data_dict["players"].union(new_players)
    data_dict["selections"][self.current_stage] = new_players.union([child_interface.label for 
                                                      child_interface in self.original_view.children
                                                      if isinstance(child_interface, discord.ui.Button)
                                                      and child_interface.style==discord.ButtonStyle.primary])
    msg = self.original_interaction.message
    await msg.delete()
    await pick_players(data_dict)

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
        "style": discord.ButtonStyle.danger})
    data_dict["buttons"][current_stage].append({
        "callback_func": collect_selection_finish,
        "label": "Continue With Current Selection",
        "style": discord.ButtonStyle.success})
    return await data_dict["thread"].send("Choose a Source!", view=SelectView(data_dict))


def players_from_selection(data_dict):
    names = set()
    for v in data_dict["selections"]["players_source"].values() :
        for m in v.members:
            player_name = data_dict["db"].json().get("dcid", "$.{}.quake_name".format(m.id))
            if player_name:
                names.add(player_name[0])
            else:
                names.add(m.display_name)
    return data_dict.get("players", set()).union(names)


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
        game_modes = {"args":{"max_values":1},
                    "options":{k:k for k in ['Sacrifice', 'Capture The Flag',"Slipgate", "Team Deathmatch", "2V2 TDM"]}}
        balance_options = {"args":{"max_values":1},
                    "options":data_dict["team_balance_options"]}
        data_dict["dropdowns"][current_stage] = [game_modes,balance_options]
        data_dict["buttons"][current_stage]=[{
            "callback_func": collect_selection_finish,
            "label": "Continue With Current Selection",
            "style": discord.ButtonStyle.success}]
        return await data_dict["thread"].send("Pick a game mode and Balance Option!", view=SelectView(data_dict))
    else:
        data_dict["balance_func"] = list(
            data_dict["team_balance_options"].values())[0]
        await data_dict["flow"][current_stage](data_dict)


async def assign_players(data_dict):
    current_stage = "assign_players"
    
    jdb = data_dict["db"].json()
    players = data_dict["selections"]["pick_players"]
    game_mode_name, game_mode = [(k,v) for k,v in data_dict["selections"]["choose_balance_func"].items() if isinstance(v,str)][0]
    balance_func_name, balance_func = [(k,v) for k,v in data_dict["selections"]["choose_balance_func"].items() if not isinstance(v,str)][0]
    players_elo = {}
    for player_name in players:
        player_elo_dict = jdb.get("qcelo", "$.{}".format(player_name))
        player_elo_dict = player_elo_dict[0] if player_elo_dict else {}
        players_elo[player_name] = player_elo_dict.get(game_mode,0) 
    
    text = f"Recomended teams for {game_mode_name} based on {balance_func_name} algorithm:\n"
    teams = await balance_func(players_elo)
    for team1, team2 in teams:
        team1 = ", ".join(team1)
        team2 = ", ".join(team2)
        text+= f"\nTeam 1:{team1}\nTeam 2:{team2}\n"
    await data_dict["channel"].send(text)
    await clean_up_msg(data_dict)


async def start_pickup(message, db):
    if message.guild:
        thread = await message.create_thread(name="Pickup Organizer", auto_archive_duration=60)
        clean_up = True
    else:
        thread = message.channel
        clean_up = False

    author = message.author
    guild = message.guild
    channel = message.channel
    roles = guilds_roles.get(guild.id, {}).get("roles")
    channels = guilds_roles.get(guild.id, {}).get("channels")
    data_dict = {
        "team_balance_options": {"Random": shuffle_list, 
                                 "Pick from top":pick_from_top, 
                                 "ELO Balanced":weighted_player_allocation},
        "message": message,
        "thread": thread,
        "author": author,
        "guild": guild,
        "channel": channel,
        "db": db,
        "roles": roles,
        "channels": channels,
        "clean_up":clean_up,
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


def mode_stats(player_stats, game_mode):
    champ_stats = {}
    objective_modes = ['GameModeObelisk', 'GameModeObeliskPro', 'GameModeCtf']
    killing_modes = ['GameModeFFA', 'GameModeTeamDeathmatch', 'GameModeDuel',  'GameModeTeamDeathmatch2vs2', 
                     'GameModeInstagib','GameModeDuelPro', 'GameModeSlipgate']
    for champ, champ_data in player_stats["playerProfileStats"]["champions"].items():
        champ_mode_data = champ_data["gameModes"][game_mode]
        champ_stats[champ] = {
            "games_count": champ_mode_data["won"] + champ_mode_data["lost"] + champ_mode_data["tie"],
            "kills": champ_mode_data["kills"], 
            "deaths": champ_mode_data["deaths"], 
            "wins": champ_mode_data["won"],
            "losses":champ_mode_data["lost"],
            "life_time": champ_mode_data["lifeTime"],
            "play_time": champ_mode_data["timePlayed"],
            "score": champ_mode_data["score"],}
    game_mode_stats = {k:sum([champ_stats[champ][k] for champ in champ_stats]) 
                     for k in ["games_count","life_time","play_time", "losses","wins","score", "kills", "deaths"]}
    if game_mode in objective_modes:
        game_mode_stats["win_ratio"] = game_mode_stats["wins"]/max(1,game_mode_stats["losses"])
    else:
        game_mode_stats["win_ratio"] = game_mode_stats["kills"]/max(1,game_mode_stats["deaths"])
    game_mode_stats["avg_score"] = game_mode_stats["score"]/max(1,game_mode_stats["games_count"])
    game_mode_stats["avg_score_per_minute"] = game_mode_stats["score"]/max(1,game_mode_stats["play_time"]/1000/60)
    game_mode_stats["mode_avg_score"] = game_mode_stats["avg_score"]/max(1,game_mode_stats["avg_score_per_minute"])
    game_mode_stats["mode_score"] = game_mode_stats["avg_score_per_minute"]*game_mode_stats["win_ratio"]
    return game_mode_stats

def mode_elo(player_stats, game_mode):
    game_mode_stats = mode_stats(player_stats,game_mode)
    return game_mode_stats["mode_score"]

async def calc_elos(data_dict):
    db = data_dict["db"]
    jdb = db.json()
    quake_name = data_dict["player_data"]["quake_name"]
    game_modes = {"Capture The Flag":'GameModeCtf',"Sacrifice":'GameModeObelisk', 
    "Deathmatch":'GameModeFFA', "Team Deathmatch":'GameModeTeamDeathmatch', 
    "2V2 TDM":'GameModeTeamDeathmatch2vs2',"Duel":'GameModeDuel',
    "Instagib":'GameModeInstagib', "Slipgate":'GameModeSlipgate',
    "Legacy Ranked Sacrifice":'GameModeObeliskPro', "Legacy Ranked Duel":'GameModeDuelPro',
     }
    objective_modes = ['Capture The Flag', 'Sacrifice', 
                        # 'Ranked Sacrifice'
                        ]
    killing_modes = ["Team Deathmatch","2V2 TDM", "Slipgate",
                    # "Instagib", "Deathmatch", 
                    # "Duel", "Ranked Duel"
                    ]

    elos = {name:mode_elo(data_dict["qcstats"], mode) for name,mode in game_modes.items()}
    avg = lambda data:sum(data)/len(data)
    elos["Objective"] = avg([v for k,v in elos.items() if k in objective_modes and v>0])
    elos["Killing"] = avg([v for k,v in elos.items() if k in killing_modes and v>0])

    jdb.set("qcelo", ".{}".format(quake_name), elos)
    db.save()
    return elos

async def clean_up_msg(data_dict):
    if data_dict["clean_up"]:
        await data_dict["thread"].delete()
        await data_dict["message"].delete()

    
async def refresh_all_players_data(data_dict, interaction=None):
    db = data_dict["db"]
    jdb = db.json()
    dcid = jdb.get("dcid")
    for discord_id,discord_user_dict in dcid.items():
        copy_dict = data_dict.copy()
        if "quake_name" in discord_user_dict:
            quake_name = discord_user_dict["quake_name"]
            copy_dict["player_data"]["quake_name"] = quake_name
            copy_dict["clean_up"] = False
            await refresh_player_data(copy_dict)
    
    
    if data_dict["clean_up"]:
        await clean_up_msg(data_dict)
    elif interaction:
        await interaction.message.delete()
    
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
    
    await jdb_set(jdb, key="qcstats", path =  ".{}".format(quake_name), value = player_stats)

    elos = await calc_elos(data_dict)
    return await show_player_stats(data_dict)
    # if data_dict["clean_up"]:
    #     await data_dict["thread"].delete()
    #     await data_dict["message"].delete()
    # elif interaction:
    #     await interaction.message.delete()
    
async def register_outsider(self, interaction, data_dict):
    return await interaction.response.send_modal(InputModal(data_dict,
                                                          original_view=self.view,
                                                          original_interaction=interaction,
                                                          callback_func=partial(get_player_name_input_callback, register=False),
                                                          input_fields=5
                                                          ))
    

async def register_new_player(self, interaction, data_dict):
    return await interaction.response.send_modal(InputModal(data_dict,
                                                          original_view=self.view,
                                                          original_interaction=interaction,
                                                          callback_func=partial(get_player_name_input_callback, register=True),
                                                          input_fields=1
                                                          ))

async def show_player_stats(data_dict, interaction = None):
    jdb = data_dict["db"].json()
    if data_dict.get("player_data",{}).get("quake_name"):
        quake_name = data_dict["player_data"]["quake_name"]
    else:
        return await data_dict["thread"].send("Error: DB entry for user id `{}` is missing your Quake name, please register first".format(data_dict["author"].id))
    elos = jdb.get("qcelo", ".{}".format(quake_name))
    text = f"{quake_name} ELO stats:\n"
    for mode, val in elos.items():
        text+="- {}: {:0.2f}\n".format(mode, val)
    await data_dict["channel"].send(text)
    if data_dict["clean_up"]:
        await clean_up_msg(data_dict)
    elif interaction:
        await interaction.message.delete()

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
                                                "callback_func": lambda self, interaction, data_dict:refresh_player_data(data_dict, 
                                                                                                                     interaction),
                                                "label": "Refresh stats",
                                                "style": discord.ButtonStyle.primary
                                                }
                                              )
        data_dict["buttons"][current_stage].append({"callback_func": lambda self, interaction, data_dict:show_player_stats(data_dict,
                                                                                                                       interaction),
                                                "label": "See Stats",
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
    data_dict["buttons"][current_stage].append({"callback_func":register_outsider,
                                                "label": "Register Outsider",
                                                "style": discord.ButtonStyle.primary
                                                }
                                              )
    if author.id==88533822521507840:
        data_dict["buttons"][current_stage].append({"callback_func": lambda self, 
                                                                    interaction, data_dict:refresh_all_players_data(data_dict,
                                                                                                                       interaction),
                                                "label": "Refresh all players stats",
                                                "style": discord.ButtonStyle.primary
                                                }
                                              )
    
    return await thread.send("What would you like to do?", view=SelectView(data_dict))
