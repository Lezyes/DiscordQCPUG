import requests
import discord
from functools import partial

from botui import InputModal, SelectView, selection_all, collect_selection_finish, button_pressed, buttons_all, collect_buttons_finish
from db_utils import jdb_set
from dc_utils import clean_up_msg

async def get_player_stats(player_tag):
    url = f"https://quake-stats.bethesda.net/api/v2/Player/Stats?name={player_tag}"
    r = requests.get(url)
    player_data = r.json()
    return player_data

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
        return await data_dict["channel"].send("Error: DB entry for user id `{}` is missing your Quake name, please register first".format(data_dict["author"].id))
    player_stats = await get_player_stats(quake_name)
    if player_stats.get("code")==404:
        return await data_dict["channel"].send("Error: 404 `{}` is resulting in a 404 from quake-stats api".format(quake_name))
    data_dict["qcstats"] = player_stats
    db = data_dict["db"]
    jdb = db.json()
    
    await jdb_set(jdb, key="qcstats", path =  ".['{}']".format(quake_name), value = player_stats)
    elos = await calc_elos(data_dict)
    return await show_player_stats(data_dict)


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



def mode_stats(player_stats, game_mode):
    champ_stats = {}
    objective_modes = ["GameModeObelisk", "GameModeObeliskPro", "GameModeCtf"]
    killing_modes = ["GameModeFFA", "GameModeTeamDeathmatch", "GameModeDuel",  "GameModeTeamDeathmatch2vs2", 
                     "GameModeInstagib","GameModeDuelPro", "GameModeSlipgate"]
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
    game_modes = {"Capture The Flag":"GameModeCtf","Sacrifice":"GameModeObelisk", 
    "Deathmatch":"GameModeFFA", "Team Deathmatch":"GameModeTeamDeathmatch", 
    "2V2 TDM":"GameModeTeamDeathmatch2vs2","Duel":"GameModeDuel",
    "Instagib":"GameModeInstagib", "Slipgate":"GameModeSlipgate",
    "Legacy Ranked Sacrifice":"GameModeObeliskPro", "Legacy Ranked Duel":"GameModeDuelPro",
     }
    objective_modes = ["Capture The Flag", "Sacrifice", 
                        # "Ranked Sacrifice"
                        ]
    killing_modes = ["Team Deathmatch","2V2 TDM", "Slipgate",
                    # "Instagib", "Deathmatch", 
                    # "Duel", "Ranked Duel"
                    ]

    elos = {name:mode_elo(data_dict["qcstats"], mode) for name,mode in game_modes.items()}
    avg = lambda data:sum(data)/len(data)
    elos["Objective"] = avg([v for k,v in elos.items() if k in objective_modes and v>0])
    elos["Killing"] = avg([v for k,v in elos.items() if k in killing_modes and v>0])

    jdb.set("qcelo", ".['{}']".format(quake_name), elos)
    db.save()
    return elos



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
    elos = jdb.get("qcelo", ".['{}']".format(quake_name))
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