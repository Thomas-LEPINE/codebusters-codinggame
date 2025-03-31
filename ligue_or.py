import sys
import math
import random

# Send your busters out into the fog to trap ghosts and bring them home!

### CONSTANTS

busters_per_player = int(input())  # the amount of busters you control
ghost_count = int(input())  # the amount of ghosts on the map
my_team_id = int(input())  # if this is 0, your base is on the top left of the map, if it is one, on the bottom right


MY_BASE_X, MY_BASE_Y = 16000 * my_team_id, 9000 * my_team_id

SEARCH_COORDINATES = [
    # Search repartition if my_team_id == 0
    [
        [(14000, 7000)],
        # [(100, 2200), (8000, 7800), (2200, 7800)],
        [(13900, 2100), (11000, 7900), (8000, 2100), (2100, 7900)],
        [(2100, 7900), (8000, 7900), (13900, 2100)],
    ],

    # Search repartition if my_team_id == 1
    [
        [(2000, 2000)],
        # [(2200, 7800), (8000, 2200), (13800, 2200)],
        [(2100, 7900), (5000, 2100), (8000, 7900), (13900, 2100)],
        [(13900, 2100), (8000, 2100), (2100, 7900)],
    ]
]

RADAR_TURN = { # {buster_id: turn} For each of my busters, give the turn to execute RADAR command
    0: 5,
    1: 10,
    2: 15,
    3: 20,
    4: 25
}

GROUPING_STRATEGY_TURN = 50 # Turn from which busters will move in group

### GLOBAL DATA

TARGET_COORD_MAP = {} # {buster_id: index} Store index of next target coordinates in SEARCH_COORDINATES for each of our busters
LAST_STUN_TURN = {} # {buster_id: turn} Store turn when one of our busters stun an enemy
LAST_KNOWN_GHOST_DATA = {} # {ghost_id: ghost_data} Store/Update data of all ghosts every time our busters see them
ALLY_CALLS = {} # {buster_id: ghost_data} Store target data when one of our busters need help




### FUNCTIONS

## Basic functions
def update_known_data(ghost_data):
    ghost_id = ghost_data["id"]

    if ghost_id in LAST_KNOWN_GHOST_DATA:
        known_data = LAST_KNOWN_GHOST_DATA[ghost_id]

        for prop in ["x", "y", "state", "value"]:
            known_data[prop] = ghost_data[prop]

        if known_data["status"] == "GONE":
            known_data["status"] = "AVAILABLE"

    else:
        ghost_data["status"] = "AVAILABLE"
        LAST_KNOWN_GHOST_DATA[ghost_id] = ghost_data

def get_buster_next_coord(turn, buster, buster_index):
    """Compute the next coordinates to target. If buster is on previous target coordinates, we send it to the next
    in its SEARCH_COORDINATES line"""

    search_coordinates_team = SEARCH_COORDINATES[my_team_id]
    # Strategy: until turn GROUPING_STRATEGY_TURN, ally busters are splitted over the map, after, they are grouped
    apply_grouping_strategy = turn > GROUPING_STRATEGY_TURN and busters_per_player > 2 and buster_index != 0
    search_coordinates_line = search_coordinates_team[1 if apply_grouping_strategy else buster_index % len(search_coordinates_team)]

    if buster["id"] in TARGET_COORD_MAP.keys():

        search_coordinates_index = TARGET_COORD_MAP[buster["id"]]

        if (buster["x"], buster["y"]) == search_coordinates_line[search_coordinates_index]:
            new_search_coordinates_index = (search_coordinates_index + 1) % len(search_coordinates_line)
            TARGET_COORD_MAP[buster["id"]] = new_search_coordinates_index
            return search_coordinates_line[new_search_coordinates_index]

    else:
       TARGET_COORD_MAP[buster["id"]] = 0
       
    return search_coordinates_line[TARGET_COORD_MAP[buster["id"]]]

def get_dist(entity1, entity2):
    return math.dist([entity1["x"], entity1["y"]], [entity2["x"], entity2["y"]])

def get_nb_turns_since_last_stun(buster, turn):
    """Get gap between current turn and last stun turn"""
    if buster["id"] not in LAST_STUN_TURN.keys():
        return math.inf
    return turn - LAST_STUN_TURN[buster["id"]]

def get_calls_from_other_busters(buster):
    """Get elements of ALLY_CALL whose key is different of buster id"""
    return dict(filter(lambda call_pair: call_pair[0] != buster["id"], ALLY_CALLS.items()))

def nb_allies_on_ghost(target_ghost):
    return len(list(filter(
        lambda buster: buster["state"] == 3 and buster["value"] == target_ghost["id"],
        my_busters
    )))

def get_available_known_ghosts():
    return list(filter(
        lambda ghost: ghost["status"] == "AVAILABLE",
        LAST_KNOWN_GHOST_DATA.values()
    ))

def get_dist_to_my_base(entity):
    return get_dist(entity, {"x": MY_BASE_X, "y": MY_BASE_Y})

def get_ejected_ghosts(buster):
    return list(filter(
        lambda ghost: ghost["status"] ==  f'EJECTED TO BUSTER {buster["id"]}',
        LAST_KNOWN_GHOST_DATA.values()
    ))

def is_ghost_not_released(ghost):
    return not ghost["status"].startswith("RELEASED")




## Score functions
def get_ghost_interest_score(turn, buster, ghost):
    """Compute interest for buster to bust ghost according to...
    * distance buster - ghost
    * ghost remaining endurance 
    * if ghost was ejected to buster or not
        ** if ghost was ejected but not to buster, score is 0
    * if turn > GROUPING_STRATEGY_TURN and ally busters are busting this ghost
    """
    return (
            # 40 * int(get_dist(buster, ghost) < 2200) \
            10 * int(get_dist(buster, ghost) < 4400) \
            + (40 - ghost["state"])
        ) * int(
            ghost["id"] not in LAST_KNOWN_GHOST_DATA \
            or not LAST_KNOWN_GHOST_DATA[ghost["id"]]["status"].startswith("EJECTED TO BUSTER")
            or LAST_KNOWN_GHOST_DATA[ghost["id"]]["status"] == f'EJECTED TO BUSTER {buster["id"]}') \
         * (1 if turn < GROUPING_STRATEGY_TURN else 1 + nb_allies_on_ghost(ghost))

def get_ally_call_interest_score(buster, call_item):
    call_id, ghost = call_item
    return - get_dist(buster, ghost)

def get_enemy_interest_score(buster, enemy):
    return int(get_dist(buster, enemy) < 2200) \
        + 3 * int(enemy["state"] == 1) \
        + int(enemy["state"] != 2)




## Strategy functions
def bust_ghost_or_get_closer(target_ghost, ghost_distance):
    if ghost_distance >= 1760:
        return f'MOVE {target_ghost["x"]} {target_ghost["y"]}'

    elif 500 < ghost_distance < 900:
        # Ghost is too close to bust it
        # Strategy: Wait ghost to move away for 1 turn
        return f'MOVE {buster["x"]} {buster["y"]}'
    
    elif ghost_distance <= 500:
        # Ghost is too close to bust it
        # Strategy: Move 500 units (354 dx, 354 dy) in direction of our base for 1 turn
        move_away_dxdy = (-1 if MY_BASE_X == 0 else 1) * 354
        return f'MOVE {target_ghost["x"] + move_away_dxdy} {target_ghost["y"] + move_away_dxdy}'

    # elif target_ghost["state"] == 0 and nb_allies_on_ghost(target_ghost) <= target_ghost["value"] != 2:
    #     # Buster is stuck because at least one enemy buster is on the same ghost
    #     # Strategy: Getting closer to the ghost to see an enemy buster until we stun him
    #     print("MOVE", target_ghost["x"], target_ghost["y"])

    else:
        return f'BUST {target_ghost["id"]}'

def default_move(buster_index, buster, ghosts):
    """Choose buster default move according to other busters situation"""

    ally_calls = get_calls_from_other_busters(buster)
    available_known_ghosts = get_available_known_ghosts()

    target_ghost_index = buster_index if turn < GROUPING_STRATEGY_TURN else 0

    if len(ally_calls) > 0:
        call_id, target_ghost = max(ally_calls.items(), key=lambda call_item: get_ally_call_interest_score(buster, call_item))

        if get_dist(buster, target_ghost) < 1760 \
        and target_ghost["id"] not in map(lambda ghost: ghost["id"], ghosts):
            # Ghost is not at call coordinates, clear ALLY_CALLS and recalling default_move
            del ALLY_CALLS[call_id]
            return default_move(buster_index, buster, ghosts)

        else:
            return f'MOVE {target_ghost["x"]} {target_ghost["y"]}'

    elif len(available_known_ghosts) > target_ghost_index:
        target_ghost = sorted(available_known_ghosts, key=lambda ghost: ghost["state"])[target_ghost_index]

        if get_dist(buster, target_ghost) < 1760 \
        and target_ghost["id"] not in map(lambda ghost: ghost["id"], ghosts):
            # Ghost is not at LAST_KNOWN_GHOST_DATA coordinates
            # Strategy: update status and recalling default_move
            LAST_KNOWN_GHOST_DATA[target_ghost["id"]]["status"] = "GONE"
            return default_move(buster_index, buster, ghosts)
    
        else:
            return f'MOVE {target_ghost["x"]} {target_ghost["y"]}'

    else:
        buster_search_coord = get_buster_next_coord(turn, buster, buster_index)
        return f'MOVE {buster_search_coord[0]} {buster_search_coord[1]}'


def attack_enemy_if_interesting(turn, i, buster, target_enemy, ghosts):
    
    # print("Buster", buster["id"], "could target enemy:", target_enemy, file=sys.stderr, flush=True)

    if target_enemy["state"] not in [0, 2] \
    and get_dist(buster, target_enemy) < 1760 \
    and get_nb_turns_since_last_stun(buster, turn) > 20 \
    and f'STUN {target_enemy["id"]}' not in my_busters_actions \
    and (
        target_enemy["state"] == 3 and target_enemy["value"] in LAST_KNOWN_GHOST_DATA and LAST_KNOWN_GHOST_DATA[target_enemy["value"]]["state"] < 6
        or target_enemy["state"] == 1
    ):
        LAST_STUN_TURN[buster["id"]] = turn
        return f'STUN {target_enemy["id"]}'
    
    elif target_enemy["state"] == 1 \
    and get_dist(buster, target_enemy) < 2200 \
    and get_nb_turns_since_last_stun(buster, turn) >= 17:
        return f'MOVE {target_enemy["x"]} {target_enemy["y"]}'

    elif len(get_available_known_ghosts()) > 0:
        return bust_ghost_if_interesting(turn, i, buster, ghosts)
    
    else:
        return default_move(i, buster, ghosts)

def bust_ghost_if_interesting(turn, i, buster, visible_ghosts):
    
    target_ghost = max(get_available_known_ghosts(), key=lambda ghost: get_ghost_interest_score(turn, buster, ghost))
    ghost_distance = get_dist(buster, target_ghost)
    
    print("Buster", buster["id"], "could bust ghost:", target_ghost["id"], "- ghost_distance:", ghost_distance, file=sys.stderr, flush=True)

    if LAST_KNOWN_GHOST_DATA[target_ghost["id"]]["status"].startswith("EJECTED TO BUSTER") \
    and LAST_KNOWN_GHOST_DATA[target_ghost["id"]]["status"] != f'EJECTED TO BUSTER {buster["id"]}':
        # Ghost was ejected but not to me
        # Strategy: ignore ghost
        return default_move(i, buster, visible_ghosts)

    elif ghost_distance > 4400:
        return default_move(i, buster, visible_ghosts)

    elif target_ghost["state"] > 3 and turn <= 5 \
    or target_ghost["state"] > 15 and turn <= 30:
        return default_move(i, buster, visible_ghosts)

    elif ghost_distance < 2200 and target_ghost["id"] not in map(lambda ghost: ghost["id"], visible_ghosts):
        LAST_KNOWN_GHOST_DATA[target_ghost["id"]]["status"] = "GONE"
        return default_move(i, buster, visible_ghosts)

    else:
        return bust_ghost_or_get_closer(target_ghost, ghost_distance)

def call_allies_if_interesting(buster, ghosts):
    
    ejected_ghosts_to_buster = get_ejected_ghosts(buster)
    for ghost in ejected_ghosts_to_buster:
        # Buster was stuned while ally eject ghost to him
        # Strategy: Remove EJECTED status to call allies
        LAST_KNOWN_GHOST_DATA[ghost["id"]]["status"] = "AVAILABLE"
    
    if len(ghosts) > 0:
        target_ghost = max(ghosts, key=lambda ghost: get_ghost_interest_score(turn, buster, ghost))

        if buster["id"] in ALLY_CALLS:
            previous_call_data = ALLY_CALLS[buster["id"]]
            new_call_data = list(filter(lambda ghost: ghost["id"] == previous_call_data["id"], ghosts))

            if len(new_call_data) == 0:
                # Target ghost in ally call is no longer available
                del ALLY_CALLS[buster["id"]]
            
            else:
                # Updating call data
                ALLY_CALLS[buster["id"]] = new_call_data[0]

        elif get_dist(buster, target_ghost) < 2200:
            ALLY_CALLS[buster["id"]] = target_ghost

def bring_back_ghost(turn, buster, enemy_busters):
    global ALLY_CALLS
    busted_ghost_id = buster["value"]
    closest_enemy = None if len(enemy_busters) == 0 \
            else min(enemy_busters, key=lambda enemy: int(enemy["state"] == 2) * math.inf + get_dist(buster, enemy))

    buster_dist_to_my_base = get_dist_to_my_base(buster)

    # Clean ALLY_CALLS
    ALLY_CALLS = dict(filter(lambda busterd_id_ghost: busterd_id_ghost[1]["id"] != busted_ghost_id, ALLY_CALLS.items()))

    # Stun enemy if threatening
    if closest_enemy != None \
    and get_dist(buster, closest_enemy) <= 1760 \
    and closest_enemy["state"] != 2 \
    and get_nb_turns_since_last_stun(buster, turn) > 20 \
    and f'STUN {closest_enemy["id"]}' not in my_busters_actions:
        # Strategy: if an enemy is visible (and not stuned) while our buster is bringing back a ghost,
        # we stun him to avoid a ghost theft
        LAST_KNOWN_GHOST_DATA[busted_ghost_id]["status"] = "AVAILABLE"
        return f'STUN {closest_enemy["id"]}'

    elif buster_dist_to_my_base < 1600:
        LAST_KNOWN_GHOST_DATA[busted_ghost_id]["status"] = "RELEASED BY ME"
        return "RELEASE"
        
    else:
        my_base_nearest_buster = min(my_busters, key=lambda buster: get_dist_to_my_base(buster))
        
        if 4000 < buster_dist_to_my_base < 8000 \
        and my_base_nearest_buster["id"] != buster["id"] \
        and my_base_nearest_buster["state"] not in [1, 2] \
        and len(get_ejected_ghosts(my_base_nearest_buster)) == 0 \
        and get_dist_to_my_base(my_base_nearest_buster) < buster_dist_to_my_base * 0.8:
            # An ally in 20% (< buster_dist_to_my_base 0.8) closer to our base, not holding ghost
            # Strategy: eject ghost to this buster if interesting
            LAST_KNOWN_GHOST_DATA[busted_ghost_id]["status"] = f'EJECTED TO BUSTER {my_base_nearest_buster["id"]}'
            LAST_KNOWN_GHOST_DATA[busted_ghost_id]["ejected_x"] = my_base_nearest_buster["x"]
            LAST_KNOWN_GHOST_DATA[busted_ghost_id]["ejected_y"] = my_base_nearest_buster["y"]
            return f'EJECT {my_base_nearest_buster["x"]} {my_base_nearest_buster["y"]}'

        else:
            LAST_KNOWN_GHOST_DATA[busted_ghost_id]["status"] = f'BROUGHT BACK BY BUSTER {buster["id"]}'
            return f'MOVE {MY_BASE_X} {MY_BASE_Y}'



## Global function
def give_action_to_buster(turn, buster_index, buster, enemy_busters, visible_ghosts):

    if buster_index == 0 and turn < 5:
        # Strategy: send 1st buster in direction of map center to execute RADAR
        buster_search_coord = get_buster_next_coord(turn, buster, buster_index)
        return f'MOVE {buster_search_coord[0]} {buster_search_coord[1]}'

    elif buster_index in RADAR_TURN \
    and turn >= RADAR_TURN[buster_index] \
    and get_dist_to_my_base(buster) > 5000:
        del RADAR_TURN[buster_index]
        return "RADAR"

    elif buster["state"] == 2:
        call_allies_if_interesting(buster, visible_ghosts)
        return f'MOVE {buster["x"]} {buster["y"]}'

    elif buster["state"] == 1:
        return bring_back_ghost(turn, buster, enemy_busters)
    
    elif len(get_ejected_ghosts(buster)) > 0:
        target_ghost = min(get_ejected_ghosts(buster), key=lambda ghost: get_dist(buster, ghost))
        return bust_ghost_or_get_closer(target_ghost, get_dist(buster, target_ghost))

    elif len(enemy_busters) > 0:
        target_enemy = max(enemy_busters, key=lambda enemy: get_enemy_interest_score(buster, enemy))
        return attack_enemy_if_interesting(turn, buster_index, buster, target_enemy, visible_ghosts)

    # elif buster["id"] in ALLY_CALLS:
    #     if get_dist(buster, ALLY_CALLS[buster["id"]]) > 1760:


    elif len(get_available_known_ghosts()) > 0:
        return bust_ghost_if_interesting(turn, buster_index, buster, visible_ghosts)

    else:
        return default_move(buster_index, buster, visible_ghosts)


turn = 0

### GAME LOOP
while True:
    entities = int(input())  # the number of busters and ghosts visible to you
    
    turn += 1
    my_busters = []
    enemy_busters = []
    visible_ghosts = []

    my_busters_actions = []
    
    for i in range(entities):
        # entity_id: buster id or ghost id
        # y: position of this buster / ghost
        # entity_type: the team id if it is a buster, -1 if it is a ghost.
        # state: For busters: 0=idle, 1=carrying a ghost.
        # value: For busters: Ghost id being carried. For ghosts: number of busters attempting to trap this ghost.
        entity_id, x, y, entity_type, state, value = [int(j) for j in input().split()]

        if entity_type == my_team_id :
            my_busters.append({"id": entity_id, "x": x, "y": y, "state": state, "value": value})
            # print("My Busters = " + str(my_busters[i]), file=sys.stderr, flush=True)

        elif entity_type == -1 :
            ghost_data = {"id": entity_id, "x": x, "y": y, "state": state, "value": value}
            visible_ghosts.append(ghost_data)
            update_known_data(ghost_data)

        else:
            enemy_busters.append({"id": entity_id, "x": x, "y": y, "state": state, "value": value})
                
    # print("Visible ghosts:", ghosts, file=sys.stderr, flush=True)

    print("LAST_KNOWN_GHOST_DATA:", file=sys.stderr, flush=True)
    for ghost_data in filter(is_ghost_not_released, sorted(LAST_KNOWN_GHOST_DATA.values(), key=lambda entity: entity["id"])):
        print(ghost_data, file=sys.stderr, flush=True)

    print("Turn:", turn, "\n", \
        "LAST_STUN_TURN:", LAST_STUN_TURN,
         file=sys.stderr, flush=True)
    print("ALLY_CALLS:", ALLY_CALLS, file=sys.stderr, flush=True)
    
    for i, buster in enumerate(my_busters):
        my_busters_actions.append(
            give_action_to_buster(turn, i, buster, enemy_busters, visible_ghosts))

    for action in my_busters_actions:
        print(action)