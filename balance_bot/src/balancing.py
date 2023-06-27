from itertools import combinations
from random import randint

async def shuffle_list(players_elo):
    l = list(players_elo.items())
    for i in range(len(l) * 2):
        r = randint(0, len(l) - 1)
        l.append(l.pop(r))
    return [(dict(l[0::2]), dict(l[1::2]))]

async def pick_from_top(players_elo):
    soreted_by_elo = sorted(players_elo.items(), key=lambda x:x[1], reverse=True)
    team1_elos = dict(soreted_by_elo[0::2])
    team2_elos = dict(soreted_by_elo[1::2])
    return [(team1_elos, team2_elos)]

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
        
        teams.append((team1_elo,team2_elo))
    return teams