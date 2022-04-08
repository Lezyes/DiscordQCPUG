import discord
import logging
from secret import token
from guild_games_roles import guilds_roles
from text_to_emojis import emoji_dict
from functools import partial
from random import randint
from asyncio import TimeoutError

logging.basicConfig(level=logging.WARNING)

# intents = discord.Intents.all()


intents = discord.Intents.none()

intents.guilds = True
intents.members = True
intents.voice_states = True
intents.messages = True
intents.reactions = True

client = discord.Client(intents=intents)


@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))
    guilds = client.guilds
    for guild in guilds:
        print(guild)

async def get_player_stats(player_tag):
    url = f"https://quake-stats.bethesda.net/api/v2/Player/Stats?name={player_tag}"
    r = requests.get(url)
    player_data = r.content
    return player_data

@client.event
async def on_reaction_add(reaction, user):
    pass

@client.event
async def on_message(message):
    # if starting pug
    if message.content.startswith('$pickup') or message.content.startswith('$pu'):
        def shuffle_list(l):
            for i in range(len(l)*2):
                r = randint(0, len(l)-1)
                l.append(l.pop(r))
            return l

        def match_emoji(selection_dict, emoji_dict, special_cases_dict=None, multiple_choice=False):
            selection_select = {}
            emoji_select = {}
            special_cases = {}
            text = ""
            emoji_options = list(emoji_dict.values())
            for i, selection in enumerate(selection_dict):
                emoji = emoji_options[i]
                selection_select[selection] = emoji
                emoji_select[emoji] = selection
                text += f"{selection}: {emoji}\n"
            if special_cases_dict:
                for selection in special_cases_dict:
                    i += 1
                    emoji = emoji_options[i]
                    selection_select[selection] = emoji
                    special_cases[emoji] = {"name":selection, "func":special_cases_dict[selection]}
                    text += f"{selection}: {emoji}\n"
            if multiple_choice:
                text += f"Finished: 👍\n"
            return text, selection_select, emoji_select, special_cases

        async def collect_reactions(reply, emoji_select, special_cases = None):
            # kinda slow?
            reply = await reply.channel.fetch_message(reply.id)
            picked_selection = set()
            for reaction in reply.reactions:
                for user in await reaction.users().flatten():
                    if message.author == user:
                        if special_cases and reaction.emoji in special_cases:
                            picked_selection = special_cases.get(reaction.emoji,{}).get("func", lambda x: x[0])(
                                                                            {"picked_selection":picked_selection,
                                                                             "emoji_select":emoji_select})
                        elif reaction.emoji in emoji_select:
                            picked_selection.add(emoji_select.get(reaction.emoji))
            return picked_selection

        async def send_selection_message(text, emoji_select, special_cases = None, reference=None, multiple_choice=False):
            reply = await message.channel.send(text, reference=reference)
            for emoji in emoji_select:
                await reply.add_reaction(emoji)
            if special_cases:
                for emoji in special_cases:
                    await reply.add_reaction(emoji)
            if multiple_choice:
                await reply.add_reaction("👍")
            return reply

        def check_reaction(reaction, user, check_message, ok_reactions):
            return user == message.author and reaction.message.id == check_message.id and str(reaction.emoji) in ok_reactions

        def check_msg(msg, check_message):
            return user == message.author and msg.reference.message_id == check_message.id

        team_balance_options = {"Random": shuffle_list}

        guild = message.guild
        channel = message.channel
        roles = guilds_roles.get(guild.id, {}).get("roles")
        channels = guilds_roles.get(guild.id, {}).get("channels")

        # get players from channels
        players = {}
        for role in guild.roles:
            if role.id in roles:
                players[role.name] = role.members
        for guild_channel in guild.channels:
            if guild_channel.id in channels:
                players[guild_channel.name] = guild_channel.members

        # select source
        special_cases_dict = {"All": lambda x:set(x.get("emoji_select",{}).values())}
        selection_text, source_select, emoji_select, special_cases = match_emoji(players, emoji_dict, special_cases_dict=special_cases_dict, multiple_choice=True)
        text = "Please Choose Player source:\n" + selection_text
        source_reply = await send_selection_message(text, emoji_select, special_cases=special_cases, reference=message, multiple_choice=True)
        check_source = partial(check_reaction, check_message=source_reply, ok_reactions=["👍"])
        try:
            reaction, user = await client.wait_for('reaction_add', timeout=600.0, check=check_source)
        except TimeoutError:
            await channel.send('You waited too long, please try again :D ')
            return 0
        sources_from_reply = await collect_reactions(source_reply, emoji_select,special_cases)
        print(source_reply)
        pu_players = {player for source in sources_from_reply for player in players[source]}
        print(pu_players)
        # collect players from source
        # pu_players = set()
        # if source == "All":
        #     for s in players:
        #         for player in players[s]:
        #             pu_players.add(player)
        # else:
        #     pu_players = set([player for player in players[source]])

        # select players
        special_cases_dict = {"All": lambda x: set(x.get("emoji_select", {}).values()),
                              "Add Players Manually": lambda x: x.get("picked_selection", set()).union(["Add Players Manually"])}
        selection_text, player_select, emoji_select, special_cases = match_emoji(pu_players, emoji_dict, special_cases_dict=special_cases_dict, multiple_choice=True)
        text = "Please Choose Players:\n" + selection_text

        players_reply = await send_selection_message(text, emoji_select, special_cases=special_cases, reference=message, multiple_choice=True)
        check_players = partial(check_reaction, check_message=players_reply, ok_reactions=["👍"])
        try:
            reaction, user = await client.wait_for('reaction_add', timeout=600.0, check=check_players)
        except TimeoutError:
            await channel.send('You waited too long, please try again :D ')
            return 0

        # collect selected players
        #Speical case for picking "All" shouldn't include "pick manually" 
        picked_players_from_reply = await collect_reactions(players_reply, emoji_select,special_cases)
        print(picked_players_from_reply)
        picked_players = {p.display_name for p in picked_players_from_reply if not isinstance(p,str) and p != "Add Players Manually"}
        if "Add Players Manually" in  picked_players_from_reply:
            text = "To add players, type their names separated by ,without spaces(example: name1,name2,name3) as a reply to this message\n"
            add_reply = await send_selection_message(text, [], reference=message)
            check_msg = partial(check_msg, check_message=add_reply)
            try:
                msg = await client.wait_for('message', timeout=600.0, check=check_msg)
            except TimeoutError:
                await channel.send('You waited too long, please try again :D ')
                return 0
            for p in msg.content.split(","):
                picked_players.add(p)

        # remove players
        while len(picked_players) > 8:
            text = 'You picked more than 8 players, please remove the extra fat:\n'
            selection_text, player_select, emoji_select, special_cases = match_emoji(picked_players, emoji_dict, multiple_choice=True)
            text += selection_text


            remove_players_reply = await send_selection_message(text, emoji_select, reference=message, multiple_choice=True)
            check_remove_players = partial(check_reaction, check_message=remove_players_reply, ok_reactions=["👍"])
            try:
                reaction, user = await client.wait_for('reaction_add', timeout=600.0, check=check_remove_players)
            except TimeoutError:
                await channel.send('You waited too long, please try again :D ')
                return 0
            picked_players_to_remove_from_reply = await collect_reactions(players_reply, emoji_select)
            picked_players_to_remove = {p.display_name for p in picked_players_to_remove_from_reply}
            picked_players = {p for p in picked_players if p not in picked_players_to_remove}

        if len(team_balance_options) > 1:
            text = 'How do you wish to balance teams?\n'
            selection_text, balance_select, emoji_select, special_cases = match_emoji(team_balance_options, emoji_dict)
            text += selection_text

            team_balance_reply = await send_selection_message(text, emoji_select, reference=message)
            check_team_balance = partial(check_reaction, check_message=team_balance_reply, ok_reactions=emoji_select)
            try:
                reaction, user = await client.wait_for('reaction_add', timeout=600.0, check=check_team_balance)
            except TimeoutError:
                await channel.send('You waited too long, please try again :D ')
                return 0
            balance_func = team_balance_options[emoji_select[str(reaction.emoji)]]
        else:
            balance_func = list(team_balance_options.values())[0]

        picked_players = balance_func(list(picked_players))
        team1 = []
        team2 = []
        for i,p in enumerate(picked_players):
            if i>=len(picked_players)//2:
                team2.append(p)
            else:
                team1.append(p)
        team1 = ", ".join(team1)
        team2 = ", ".join(team2)
        await channel.send(f"Team 1:{team1}\nTeam 2:{team2} ")


client.run(token)
