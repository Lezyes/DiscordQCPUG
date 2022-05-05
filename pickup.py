import discord
from botui import InputModal, SelectView, selection_all, collect_selection_finish, button_pressed, buttons_all, collect_buttons_finish
from guild_games_roles import guilds_roles
import json
from functools import partial

from balancing import shuffle_list, pick_from_top, weighted_player_allocation
from db_utils import jdb_set, jdb_get
from dc_utils import clean_up_msg

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
    text = ""
    players_elo = {}
    for player_name in players:
        player_elo_dict = jdb.get("qcelo", "$.{}".format(player_name))
        if player_elo_dict:
            player_elo_dict = player_elo_dict[0]
        else:
            player_elo_dict = {}
            text+=f"{player_name} isn't in the DB, "
        players_elo[player_name] = player_elo_dict.get(game_mode,0) 
    
    text += f"\nRecomended teams for {game_mode_name} based on {balance_func_name} algorithm:\n"
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
