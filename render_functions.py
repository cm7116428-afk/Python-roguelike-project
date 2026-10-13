"""Renders the GUI"""

import tcod
import numpy as np
import tcod.ecs
from game.components import DungeonFloor,Experience,Position,Gold,Graphic,Fighter,MapTiles,MapVisible,MapExplored
from game.tags import IsActor, IsItem, IsPlayer

def render_all(
        world:tcod.ecs.Registry,
        active_map:tcod.ecs.Entity,
        root_console:tcod.console.Console,
        screen_width: int,
        screen_height: int,
) -> None:
    """System that clears the display and dynamically renders the entire UI layout"""
    #Clear entire console screen buffer first
    root_console.clear(fg=(0,0,0),bg=(0,0,0))

    #1 Render game map
    tiles = active_map.components[MapTiles]
    visible_mask = active_map.components[MapVisible]
    explored_mask = active_map.components[MapExplored]

    #Draw static terrain map tiles
    for y in range(tiles.shape[0]):
        for x in range(tiles.shape[1]):
            tile = tiles[y,x]
            if visible_mask[y,x]:
                #Draw illuminated tiles inside FOV
                root_console.print(x=x,y=y,text=chr(tile["ch"]),fg=tuple(tile["fg"]),bg=tuple(tile["bg"]))
            elif explored_mask[y,x]:
                #Draw faded tiles outside of FOV
                faded_fg = (int(tile["fg"][0]*0.3),int(tile["fg"][1]*0.3),int(tile["fg"][2]*0.3))
                root_console.print(x=x,y=y,text=chr(tile["ch"]),fg=faded_fg,bg=(0,0,0))
    
    #2 Render visible entities
    #Query all entities that possess a physical layout component
    base_query = world.Q.all_of(components=[Position,Graphic])
    #Filter to current map and include the player just in case
    entities = [
        entity for entity in base_query
        if entity.relation_tag.get("InMap") == active_map or IsPlayer in entity.tags
    ]
    #Sort so corpses draw first, living entities on top
    sorted_entities = sorted(
        entities,
        key=lambda e: 0 if IsPlayer in e.tags else (
                      1 if IsActor in e.tags else (
                      2 if IsItem in e.tags else
                      3)),
                      reverse=True
        )
    for entity in sorted_entities:
        pos = entity.components[Position]
        #Only render object if it resides inside player's FOV
        if pos is not None:
            if visible_mask[pos.y,pos.x]:
                graphic = entity.components[Graphic]
                root_console.print(x=pos.x,y=pos.y,text=chr(graphic.ch),fg=graphic.fg)
    
    #3 Render player health bar
    player_query = list(world.Q.all_of(tags=[IsPlayer],components=[Fighter, Experience]))
    if player_query:
        player = player_query[0]
        fighter = player.components[Fighter]
        xp_tracker = player.components[Experience]
        gold_tracker = player.components[Gold]
        bar_y = screen_height - 4
        bar_width = 20
        root_console.draw_rect(x=0, y=bar_y, width=screen_width, height=1, ch=ord(" "), fg=(0,0,0), bg=(0,0,0))

        if fighter.hp > 0 and fighter.max_hp > 0:
            filled_width = int(float(fighter.hp)/fighter.max_hp*bar_width)
        else:
            filled_width = 0
        #Draw base background tracking element block
        root_console.draw_rect(x=0,y=bar_y,width=bar_width,height=1,ch=ord(" "),bg=(100,0,0))
        if filled_width >0:
            #Draw bright filled status metric directly over top
            root_console.draw_rect(x=0,y=bar_y,width=filled_width,height=1,ch=ord(" "),bg=(0,180,0))
        #Draw status text readout on top of tracking bar overlay
        display_hp = max(0,fighter.hp)
        hp_string = f"HP: {display_hp}/{fighter.max_hp}"
        root_console.print(x=1,y=bar_y,text=hp_string,fg=(255,255,255))

        floor_comp = active_map.components.get(DungeonFloor)
        floor_num = floor_comp.level if floor_comp else 1

        stats_y = screen_height - 4
        stats_string = f"LVL: {xp_tracker.level} | XP: {xp_tracker.current_xp}/{xp_tracker.xp_to_next_level} | Gold: {gold_tracker} | Depth: B{floor_num}"
        root_console.print(x=30,y=stats_y,text=stats_string,fg=(255,215,0))
    
    #4 Render scrolling message log
    messages = world[None].components.get(("MessageLog",list),[])
    log_y = screen_height-3
    log_height = 3
    #Draw only most recent strings that fit inside display box area
    visible_messages = messages[-log_height:]
    for idx,message in enumerate(visible_messages):
        root_console.print(x=22,y=log_y+idx,string=message,fg=(255,255,255))