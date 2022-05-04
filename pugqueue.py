

async def queue_up(message, db):
    jdb = db.json()


    game_modes = ["Capture The Flag","Sacrifice",
    "Slipgate", "Clan Arena",
    "Team Deathmatch", "Duel", 
    # "FFA Deathmatch", "Unholy Trinity", "Instagib", 
    ]
    if message.guild:
        thread = await message.create_thread(name="Pickup Organizer", auto_archive_duration=60)
        clean_up = True
    else:
        thread = message.channel
        clean_up = False

    current_stage = "start_queue_up"
    author = message.author
    guild = message.guild
    channel = message.channel
    player_data = jdb.get("dcid", "$.{}".format(author.id))
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

    if not player_data:
        data_dict["buttons"][current_stage].append({"callback_func":register_new_player,
                                                "label": "Register Quake Name",
                                                "style": discord.ButtonStyle.primary
                                                }
                                              )
        data_dict["thread"].send("Please register your Quake name before trying to queue for a pickup", view=SelectView(data_dict))

async def drop_from_queue(message,db):
    pass