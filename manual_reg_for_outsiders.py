
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
            "life_time": champ_mode_data["lifeTime"],
            "score": champ_mode_data["score"],}
    game_mode_stats = {k:sum([champ_stats[champ][k] for champ in champ_stats]) 
                     for k in ["games_count","life_time", "wins","score", "kills", "deaths"]}
    if game_mode in objective_modes:
        game_mode_stats["win_ratio"] = game_mode_stats["wins"]/max(1,game_mode_stats["games_count"])
    else:
        game_mode_stats["win_ratio"] = game_mode_stats["kills"]/max(1,game_mode_stats["kills"]+ game_mode_stats["deaths"])
    game_mode_stats["avg_score"] = game_mode_stats["score"]/max(1,game_mode_stats["games_count"])
    game_mode_stats["avg_score_per_minute"] = game_mode_stats["score"]/max(1,game_mode_stats["life_time"]/1000/60)
    game_mode_stats["mode_avg_score"] = game_mode_stats["avg_score"]/max(1,game_mode_stats["avg_score_per_minute"])
    game_mode_stats["mode_score"] = game_mode_stats["avg_score_per_minute"]*game_mode_stats["win_ratio"]
    return game_mode_stats

def mode_elo(player_stats, game_mode):
    game_mode_stats = mode_stats(player_stats,game_mode)
    return game_mode_stats["mode_score"]

def calc_elos(quake_name, player_stats):
    jdb = db.json()
    game_modes = {"Capture The Flag":'GameModeCtf',"Sacrifice":'GameModeObelisk', 
    "Deathmatch":'GameModeFFA', "Team Deathmatch":'GameModeTeamDeathmatch', "Duel":'GameModeDuel',
    "Instagib":'GameModeInstagib', "Slipgate":'GameModeSlipgate',
    "Ranked Sacrifice":'GameModeObeliskPro', "Ranked Duel":'GameModeDuelPro',
    "2V2 TDM":'GameModeTeamDeathmatch2vs2',
     }
    objective_modes = ['Capture The Flag', 'Sacrifice', 
                        # 'Ranked Sacrifice'
                        ]
    killing_modes = ["Team Deathmatch","2V2 TDM", "Slipgate",
                    # "Instagib", "Deathmatch", 
                    # "Duel", "Ranked Duel"
                    ]

    elos = {name:mode_elo(player_stats, mode) for name,mode in game_modes.items()}
    avg = lambda data:sum(data)/len(data)
    elos["Objective"] = avg([v for k,v in elos.items() if k in objective_modes and v>0])
    elos["Killing"] = avg([v for k,v in elos.items() if k in killing_modes and v>0])

    jdb.set("qcelo", ".{}".format(quake_name), elos)
    db.save()
    return elos
def get_player_stats(player_tag):
    url = f"https://quake-stats.bethesda.net/api/v2/Player/Stats?name={player_tag}"
    r = requests.get(url)
    player_data = r.json()
    return player_data

def refresh_player_data(names):
    for quake_name in names:
        
        player_stats = get_player_stats(quake_name)
        
        jdb = db.json()
        
        jdb.set("qcstats", ".{}".format(quake_name), player_stats)

        elos = calc_elos(quake_name,player_stats)
db = redis.Redis(host='localhost', port=6379, db=0)
refresh_player_data(["vld7", "evilhf"])