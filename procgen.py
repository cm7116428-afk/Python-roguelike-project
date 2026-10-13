"""Procedurally generate levels"""
from __future__ import annotations
import random
import numpy as np
import tcod.ecs
from game import entity_factories
from game.components import DungeonFloor,Graphic,Position,MapTiles,MapVisible,MapExplored,tile_dt
from game.tags import IsMap, IsItem, IsMonster,IsStairs
from typing import Iterator,List,Tuple

#Graphic definitions for tile assets
WALL_TILE = np.array((ord("#"),(100,100,100),(0,0,0)),dtype=tile_dt)
FLOOR_TILE = np.array((ord("."),(200,200,200),(25,25,25)),dtype=tile_dt)

#Difficulty scaling tables
max_monsters_by_floor = [(1,2),(4,3),(6,5)]
max_items_by_floor = [(1,1),(4,2)]
max_merchants_by_floor = [(1,1),(10,2),(20,2)]

#Weighted monster spawn pools per floor
monster_chances = {
    1: [(entity_factories.spawn_orc,80)],
    3: [(entity_factories.spawn_troll,15)],
    5: [(entity_factories.spawn_troll,30)],
    7: [(entity_factories.spawn_troll,60)],
}

merchant_chances = {
    1: [(entity_factories.spawn_merchant,1)],
    10: [(entity_factories.spawn_merchant,5)],
    20: [(entity_factories.spawn_merchant,15)]
}

#Weighted item spawn pools per floor
item_chances = {
    1: [(entity_factories.spawn_gold,65),(entity_factories.spawn_healing_potion,25),(entity_factories.spawn_chest,10)],
    4: [(entity_factories.spawn_lightning_scroll,25),(entity_factories.spawn_sword,5)],
    6: [(entity_factories.spawn_fireball_scroll,25),(entity_factories.spawn_sword,15),(entity_factories.spawn_chain_mail,10)],
    8: [(entity_factories.spawn_chain_lightning_scroll,10),(entity_factories.spawn_sword,30),(entity_factories.spawn_chain_mail,20)],
}

#Could add separate scroll and equipment spawn weight

class RectangularRoom:
    def __init__(self,x:int,y:int,width:int,height:int):
        self.x1=x
        self.y1=y
        self.x2=x+width
        self.y2=y+height
    
    @property
    def center(self) -> Tuple[int,int]:
        center_x=(self.x1+self.x2)//2
        center_y=(self.y1+self.y2)//2
        return center_x,center_y
    
    @property
    def inner(self) -> Tuple[slice,slice]:
        """Returns the inner area of this room as a NumPy slice"""
        #Add a +1 padding offset to leave outer perimeter wall structures intact
        return slice(self.y1+1,self.y2),slice(self.x1+1,self.x2)

    def intersects(self,other:RectangularRoom) -> bool:
        """Returns True if this room overlaps with another room"""
        return (
            self.x1 <= other.x2
            and self.x2 >= other.x1
            and self.y1 <= other.y2
            and self.y2 >= other.y1
        )   

def tunnel_between(start:Tuple[int,int],end:Tuple[int,int]) -> Iterator[Tuple[int,int]]:
    """Return an L-shaped tunnel path between two map coordinates"""
    x1,y1 = start
    x2,y2 = end
    #Randomly choose between a horizontal-then-vertical path or vice versa
    if random.random() < 0.5:
        corner_x,corner_y = x2,y1
    else:
        corner_x,corner_y = x1,y2
    
    #Draw lines using tcod's integrated Bresenham line generator
    for x,y in tcod.los.bresenham((x1,y1),(corner_x,corner_y)).tolist():
        yield x,y
    for x,y in tcod.los.bresenham((corner_x,corner_y),(x2,y2)).tolist():
        yield x,y

def get_max_value_for_floor(weighted_chances:List[Tuple[int,int]],floor:int) -> int:
    """Returns scaled maximum parameter ceiling based on current floor depth"""
    current_value = 0
    for floor_minimum,value in weighted_chances:
        if floor >= floor_minimum:
            current_value = value
        else:
            break
    return current_value

def get_floor_spawn_pool(pool_table:dict,floor:int) -> Tuple[list,list]:
    """Assembles a live list of valid factories and their flattened probability weights."""
    entities = []
    weights = []
    for floor_minimum in sorted(pool_table.keys()):
        if floor >= floor_minimum:
            for factory,weight in pool_table[floor_minimum]:
                if factory in entities:
                    idx = entities.index(factory)
                    weights[idx] = weight
                else:
                    entities.append(factory)
                    weights.append(weight)
        else:
            break
    return entities, weights

def generate_dungeon(
        world:tcod.ecs.Registry,
        map_width:int,
        map_height:int,
        max_rooms:int,
        room_min_size:int,
        room_max_size:int,
        floor_number: int
        ) -> Tuple[tcod.ecs.Entity,Tuple[int,int]]:
    """Generates a randomized dungeon floor, scaled to floor difficulty."""
    
    #1 Initialize empty map container
    map_entity = world.new_entity()
    map_entity.tags.add(IsMap)

    map_entity.components[DungeonFloor] = DungeonFloor(level=floor_number)

    tiles = np.full((map_height,map_width),fill_value=WALL_TILE,dtype=tile_dt)
    visible = np.zeros((map_height,map_width),dtype=bool)
    explored = np.zeros((map_height,map_width),dtype=bool)

    rooms: List[RectangularRoom]=[]
    player_start=(0,0)

    max_monsters_per_room = get_max_value_for_floor(max_monsters_by_floor,floor_number)
    max_items_per_room = get_max_value_for_floor(max_items_by_floor,floor_number)
    max_merchants = get_max_value_for_floor(max_merchants_by_floor,floor_number)

    monster_factories, monster_weights = get_floor_spawn_pool(monster_chances,floor_number)
    item_factories, item_weights = get_floor_spawn_pool(item_chances,floor_number)
    merchant_factories, merchant_weights = get_floor_spawn_pool(merchant_chances,floor_number)

    #2 Iterate through maximum attempt count to place rooms safely
    for _ in range(max_rooms):
        w=random.randint(room_min_size,room_max_size)
        h=random.randint(room_min_size,room_max_size)

        x=random.randint(0,map_width-w-1)
        y=random.randint(0,map_height-h-1)

        new_room=RectangularRoom(x,y,w,h)

        if any(new_room.intersects(other_room) for other_room in rooms):
            continue

        #Carve room inner bounds directly out of numpy wall array
        tiles[new_room.inner]=FLOOR_TILE

        if len(rooms)==0:
            player_start=new_room.center
        else:
            #Dig out a corridor connecting the new room to the preceding room
            for t_x,t_y in tunnel_between(rooms[-1].center,new_room.center):
                tiles[t_y,t_x]=FLOOR_TILE
        
        rooms.append(new_room)

        #Place items and enemies
        
        if len(rooms) > 1:
            y_slice, x_slice = new_room.inner
            x_range = range(x_slice.start,x_slice.stop)
            y_range = range(y_slice.start, y_slice.stop)
            
            #Spawn items
            num_items = random.randint(0,max_items_per_room)
            for _ in range(num_items):
                item_x = random.choice(x_range)
                item_y = random.choice(y_range)
                item_pos = Position(x=item_x,y=item_y)
                if not list(world.Q.all_of(tags=[item_pos,IsItem])):
                    chosen_item_factory = random.choices(item_factories,weights=item_weights)[0]
                    chosen_item_factory(world,map_entity,item_pos)
            #Spawn monsters
            num_monsters = random.randint(0,max_monsters_per_room)
            for _ in range(num_monsters):
                monster_x = random.choice(x_range)
                monster_y = random.choice(y_range)
                monster_pos = Position(x=monster_x,y=monster_y)
                if list(world.Q.all_of(tags=[monster_pos])):
                    continue
                chosen_monster_factory = random.choices(monster_factories,weights=monster_weights)[0]
                chosen_monster_factory(world,map_entity,monster_pos)
            #Spawn merchants
            num_merch = random.randint(0,max_merchants)
            for _ in range(num_merch):
                merch_x = random.choice(x_range)
                merch_y = random.choice(y_range)
                merch_pos = Position(x=merch_x,y=merch_y)
                if not list(world.Q.all_of(tags=[merch_pos,IsItem,IsMonster])):
                    chosen_merchant_factories = random.choices(merchant_factories,weights=merchant_weights)[0]
                    chosen_merchant_factories(world,map_entity,merch_pos)
                
    #Place down staircase in last room generated
    if rooms:
        stairs_x, stairs_y = rooms[-1].center
        stairs_pos = Position(x=stairs_x,y=stairs_y)
        #Instantiate stairs as an entity tied to this specific map floor
        entity_factories.spawn_downstairs(world,map_entity,stairs_pos)
    #After going downstairs, place up stairs at player spawn - alter later so player can go up a tower instead of down a dungeon?
    if rooms and floor_number > 1:
        up_x,up_y = player_start
        up_pos = Position(x=up_x,y=up_y)
        entity_factories.spawn_upstairs(world,map_entity,up_pos)
        
    #3 Mount populated structures back onto the active ECS entity registry
    map_entity.components[MapTiles] = tiles
    map_entity.components[MapVisible] = visible
    map_entity.components[MapExplored] = explored

    return map_entity,player_start


