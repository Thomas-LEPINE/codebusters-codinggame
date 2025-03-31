import sys
import math
import random

# Send your busters out into the fog to trap ghosts and bring them home!

busters_per_player = int(input())  # the amount of busters you control
ghost_count = int(input())  # the amount of ghosts on the map
my_team_id = int(input())  # if this is 0, your base is on the top left of the map, if it is one, on the bottom right

my_base_x, my_base_y = 16000 * my_team_id, 9000 * my_team_id

### CONSTANTS
SEARCH_COORDINATES = [
    # Search repartition if my_team_id == 0
    [
        [(14000, 7000)],
        # [(100, 2200), (8000, 7800), (2200, 7800)],
        [(13900, 2100), (11000, 7900), (8000, 2100)],
        [(2100, 7900), (8000, 7900), (13900, 2100)],
    ],

    # Search repartition if my_team_id == 1
    [
        [(2000, 2000)],
        # [(2200, 7800), (8000, 2200), (13800, 2200)],
        [(2100, 7900), (5000, 2100), (8000, 7900)],
        [(13900, 2100), (8000, 2100), (2100, 7900)],
    ]
]

TARGET_COORD_MAP = {} # Store index of next target coordinates for each of our busters
LAST_STUN_TURN = {} # Store turn when one of our busters stun an enemy
LAST_KNOWN_GHOST_DATA = {} # Store/Update data of all ghosts every time our busters see them
ALLY_CALLS = {} # Store target data when one of our busters need help

### FUNCTIONS

## Basic functions
def update_known_data(ghost_data):
    ghost_id = ghost_data["id"]
    if ghost_id in LAST_KNOWN_GHOST_DATA:
        known_data = LAST_KNOWN_GHOST_DATA[ghost_id]
        for prop in ["x", "y", "state", "value"]:
            known_data[prop] = ghost_data[prop]
    else:
        ghost_data["status"] = "AVAILABLE"
        LAST_KNOWN_GHOST_DATA[ghost_id] = ghost_data

def get_buster_next_coord(buster, i):
    """Compute the next coordinates to target. If buster is on previous target coordinates, we send it to the next
    in its SEARCH_COORDINATES line"""

    search_coordinates_team = SEARCH_COORDINATES[my_team_id]
    search_coordinates_line = search_coordinates_team[i % len(search_coordinates_team)]

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

## Score functions
def get_ghost_interest_score(buster, ghost):
    return 40 * int(get_dist(buster, ghost) < 2200) + (40 - ghost["state"])

def get_ally_call_interest_score(buster, call_item):
    call_id, ghost = call_item
    return - get_dist(buster, ghost)

def get_enemy_interest_score(buster, enemy):
    return int(get_dist(buster, enemy) < 2200) + int(enemy["state"] == 1) + int(enemy["state"] != 1)

## Strategy functions
def attack_enemy_if_interesting(turn, i, buster, target_enemy, ghosts):

    if target_enemy["state"] != 2 \
    and get_dist(buster, target_enemy) < 1760 \
    and get_nb_turns_since_last_stun(buster, turn) > 20:
        LAST_STUN_TURN[buster["id"]] = turn
        print("STUN", target_enemy["id"])
    
    elif target_enemy["state"] != 2 \
    and get_dist(buster, target_enemy) < 2200 \
    and get_nb_turns_since_last_stun(buster, turn) >= 15:
        print("MOVE", target_enemy["x"], target_enemy["y"])

    elif len(ghosts) > 0:
        bust_ghost_if_interesting(turn, i, buster, ghosts)
    
    else:
        default_move(i, buster, ghosts)

def bust_ghost_if_interesting(turn, i, buster, ghosts):
    
    target_ghost = max(ghosts, key=lambda ghost: get_ghost_interest_score(buster, ghost))
    ghost_distance = get_dist(buster, target_ghost)

    if ghost_distance > 3000:
        default_move(i, buster, ghosts)

    elif target_ghost["state"] > 3 and turn < 30:
        default_move(i, buster, ghosts)

    elif ghost_distance >= 1760:
        print("MOVE", target_ghost["x"], target_ghost["y"])
    
    elif ghost_distance <= 900:
        # Ghost is too close to bust it
        # Strategy: Move in direction of our base for 1 turn
        print("MOVE", my_base_x, my_base_y)

    elif target_ghost["state"] == 0 and nb_allies_on_ghost(target_ghost) <= target_ghost["value"] != 2:
        # Buster is stuck because at least one enemy buster is on the same ghost
        # Strategy: Getting closer to the ghost to see an enemy buster until we stun him
        print("MOVE", target_ghost["x"], target_ghost["y"])

    else:
        print("BUST", target_ghost["id"])

def call_allies_if_interesting(buster, ghosts):
    
    if len(ghosts) > 0:
        target_ghost = max(ghosts, key=lambda ghost: get_ghost_interest_score(buster, ghost))

        if buster["id"] in ALLY_CALLS and target_ghost["id"] != ALLY_CALLS[buster["id"]]:
            # Target ghost in ally call is no longer available
            del ALLY_CALLS[buster["id"]]

        elif target_ghost["state"] > 10 and get_dist(buster, target_ghost) < 2200:
            ALLY_CALLS[buster["id"]] = target_ghost

def default_move(i, buster, ghosts):
    """Choose buster default move according to other busters situation"""

    ally_calls = get_calls_from_other_busters(buster)
    if len(ally_calls) > 0:
        call_id, target_ghost = max(ally_calls.items(), key=lambda call_item: get_ally_call_interest_score(buster, call_item))

        if get_dist(buster, target_ghost) < 1760 \
        and target_ghost["id"] not in map(lambda ghost: ghost["id"], ghosts):
            # Ghost is not at call coordinates, clear ALLY_CALLS and recalling default_move
            del ALLY_CALLS[call_id]
            default_move(i, buster, ghosts)

        else:
            print("MOVE", target_ghost["x"], target_ghost["y"])

    else:
        buster_search_coord = get_buster_next_coord(buster, i)
        print("MOVE", buster_search_coord[0], buster_search_coord[1])


## Global function
def give_action_to_buster(turn, i, buster, enemy_busters, ghosts):
    if buster["state"] == 2:
        call_allies_if_interesting(buster, ghosts)
        print("MOVE", buster["x"], buster["y"])

    elif buster["state"] == 1:

        busted_ghost_id = buster["value"]

        if get_dist(buster, {"x": my_base_x, "y": my_base_y}) < 1600:
            print("RELEASE")
            LAST_KNOWN_GHOST_DATA[busted_ghost_id]["status"] = "RELEASED BY ME"
            
        else:
            print("MOVE", my_base_x, my_base_y)
            LAST_KNOWN_GHOST_DATA[busted_ghost_id]["status"] = "BROUGHT BACK BY BUSTER " + str(buster["id"])

    elif len(enemy_busters) > 0:
        ##### TODO : Improve enemy interest score
        target_enemy = max(enemy_busters, key=lambda enemy: get_enemy_interest_score(buster, enemy))
        attack_enemy_if_interesting(turn, i, buster, target_enemy, ghosts)

    # elif buster["id"] in ALLY_CALLS:
    #     if get_dist(buster, ALLY_CALLS[buster["id"]]) > 1760:


    elif len(ghosts) > 0:
        bust_ghost_if_interesting(turn, i, buster, ghosts)

    else:
        default_move(i, buster, ghosts)


turn = 0

### GAME LOOP
while True:
    entities = int(input())  # the number of busters and ghosts visible to you
    
    turn += 1
    my_busters = []
    enemy_busters = []
    ghosts = []
    
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
            ghosts.append(ghost_data)
            update_known_data(ghost_data)

        else:
            enemy_busters.append({"id": entity_id, "x": x, "y": y, "state": state, "value": value})
                
    print("Visible ghosts:", ghosts, file=sys.stderr, flush=True)
    # print("LAST_KNOWN_GHOST_DATA:", LAST_KNOWN_GHOST_DATA, file=sys.stderr, flush=True)
    print("Turn:", turn, "\n", \
        "LAST_STUN_TURN:", LAST_STUN_TURN,
         file=sys.stderr, flush=True)
    print("ALLY_CALLS:", ALLY_CALLS, file=sys.stderr, flush=True)
    
    for i, buster in enumerate(my_busters):

        give_action_to_buster(turn, i, buster, enemy_busters, ghosts)

        
      
    # print("TARGET_COORD_MAP =", TARGET_COORD_MAP, file=sys.stderr, flush=True)
