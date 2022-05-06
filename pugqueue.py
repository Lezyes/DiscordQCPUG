import discord
from botui import SelectView,collect_selection_finish
from db_utils import jdb_set, jdb_get
from dc_utils import clean_up_msg
from balancing import weighted_player_allocation


async def queue_up(message, db):
    jdb = db.json()

    if message.guild:
        thread = await message.create_thread(name="Pickup Organizer", auto_archive_duration=60)
        clean_up = True
    else:
        thread = message.channel
        clean_up = False

    current_stage = "queue_up"
    author = message.author
    guild = message.guild
    channel = message.channel
    player_data = await jdb_get(jdb,"dcid", "$.{}".format(author.id))
    if not player_data:
        data_dict["buttons"][current_stage].append({"callback_func":register_new_player,
                                                "label": "Register Quake Name",
                                                "style": discord.ButtonStyle.primary
                                                }
                                              )
        return await data_dict["thread"].send("Please register your Quake name before trying to queue for a pickup", view=SelectView(data_dict))
    else:
        player_data = player_data[0]
    data_dict = {
        "current_stage":current_stage,
        "message": message,
        "thread": thread,
        "author": author,
        "guild": guild,
        "channel": channel,
        "player_data":player_data,
        "db": db,
        "clean_up":clean_up,
        "selected_players": set(),
        "players": set(),
        "selections": {},
        "dropdowns": {},
        "buttons": {},
    }

    game_modes = {"args":{"max_values":1},
                    "options":{k:k for k in ["Capture The Flag","Sacrifice",
                                            "Slipgate", "Clan Arena",
                                            "Team Deathmatch", "Duel", 
                                            # "FFA Deathmatch", "Unholy Trinity", "Instagib", 
                                            ]}}
    players_in_team = {"args":{"max_values":1},
                "options":{str(i):i for i in range(1,5)}}
    data_dict["dropdowns"][current_stage] = [game_modes,players_in_team]



    data_dict["flow"] = {current_stage: register_to_queue,
                         }
    data_dict["buttons"][current_stage] = [{
        "callback_func": collect_selection_finish,
        "label": "Continue With Current Selection",
        "style": discord.ButtonStyle.success}]

    return await data_dict["thread"].send("Pick a Queue!", view=SelectView(data_dict))

async def register_to_queue(data_dict):
    current_stage = "register_to_queue"
    text = ""
    jdb = data_dict["db"].json()
    quake_name = data_dict["player_data"]["quake_name"]
    game_mode = [k for k,v in data_dict["selections"]["queue_up"].items() if isinstance(v,str)][0]
    team_size = [k for k,v in data_dict["selections"]["queue_up"].items() if isinstance(v,int)][0]
    queue = f"{game_mode} {team_size}v{team_size}"
    queue_cap = int(team_size)*2
    queue_state = await jdb_get(jdb, "queue", f"$.['{queue}']")
    if not queue_state:
        queue_state = []
    else:
        queue_state = queue_state[0]
    if quake_name not in queue_state:
        queue_state.append(quake_name)
    if len(queue_state)==queue_cap:
        await jdb_set(jdb, "queue", path = f"$.['{queue}']", value =  [])
        
        players_elo = {}
        for player_name in queue_state:
            player_elo_dict = await jdb_get(jdb,"qcelo", "$.['{}']".format(player_name))
            if player_elo_dict:
                player_elo_dict = player_elo_dict[0]
            else:
                player_elo_dict = {}
                text+=f"{player_name} isn't in the DB, "
            players_elo[player_name] = player_elo_dict.get(game_mode,0)
        text += f"\nRecomended teams for {game_mode_name} based on {balance_func_name} algorithm:\n"
        teams = await weighted_player_allocation(players_elo)
        # for team1, team2 in teams:
        team1, team2 = teams[0]
        team1 = ", ".join(team1)
        team2 = ", ".join(team2)
        text+= f"\nTeam 1:{team1}\nTeam 2:{team2}\n"
        
    else:
        await jdb_set(jdb, "queue", path = f"$.['{queue}']", value = queue_state)
        text += "{}: {}".format(queue, ",".join(queue_state))
    await data_dict["channel"].send(text)
    await clean_up_msg(data_dict)


async def drop_from_queue(message,db):
    jdb = db.json()

    if message.guild:
        thread = await message.create_thread(name="Pickup Organizer", auto_archive_duration=60)
        clean_up = True
    else:
        thread = message.channel
        clean_up = False

    current_stage = "queue_up"
    author = message.author
    guild = message.guild
    channel = message.channel
    player_data = await jdb_get(jdb,"dcid", "$.{}".format(author.id))
    if not player_data:
        data_dict["buttons"][current_stage].append({"callback_func":register_new_player,
                                                "label": "Register Quake Name",
                                                "style": discord.ButtonStyle.primary
                                                }
                                              )
        return await data_dict["thread"].send("Please register your Quake name before trying to queue for a pickup", view=SelectView(data_dict))
    
    player_data = player_data[0]
    quake_name = player_data["quake_name"]
    in_queues = []
    queues = await jdb_get(jdb,"queue", "$")
    if not queues:
        queues = {}
    else:
        queues = queues[0]
    nqueues = {}
    for queue, players in queues.items():
        if quake_name in players:
            in_queues.append(queue)
            nqueues[queue] = [p for p in players if p!=quake_name]
    await jdb_set(jdb, "queue", path = "$", value = nqueues)
    
    return await thread.send("Dropped from queues: {}".format(",".join(in_queues)))

async def show_queue(message,db):
    jdb = db.json()

    if message.guild:
        thread = await message.create_thread(name="Pickup Organizer", auto_archive_duration=60)
        clean_up = True
    else:
        thread = message.channel
        clean_up = False

    current_stage = "queue_up"
    author = message.author
    guild = message.guild
    channel = message.channel
    player_data = await jdb_get(jdb,"dcid", "$.{}".format(author.id))
    if not player_data:
        data_dict["buttons"][current_stage].append({"callback_func":register_new_player,
                                                "label": "Register Quake Name",
                                                "style": discord.ButtonStyle.primary
                                                }
                                              )
        return await data_dict["thread"].send("Please register your Quake name before trying to queue for a pickup", view=SelectView(data_dict))
    
    player_data = player_data[0]
    quake_name = player_data["quake_name"]
    text = "Current active queues:\n"
    queues = await jdb_get(jdb,"queue", "$")
    if not queues:
        queues = {}
    else:
        queues = queues[0]
    for queue, players in queues.items():
        if players:
            text+= "{}: {}\n".format(queue, ",".join(players))
    
    return await thread.send(text)