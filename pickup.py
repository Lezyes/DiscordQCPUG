import discord
from botui import SelectView, selection_all, collect_selection_finish, button_pressed, buttons_all, collect_buttons_finish
from guild_games_roles import guilds_roles
from random import randint

def shuffle_list(l):
    for i in range(len(l) * 2):
        r = randint(0, len(l) - 1)
        l.append(l.pop(r))
    return l[0::2], l[1::2]


async def add_players_manually(self, interaction, data_dict):
    items = self.view.children
    await interaction.response.send_modal(AddPlayersModal(data_dict,
                                                          original_view=self.view,
                                                          original_interaction=interaction))


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
    await data_dict["thread"].delete()
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
