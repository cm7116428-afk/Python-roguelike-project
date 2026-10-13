"""Collection of game states: Main Menu, the GameplayState main loop, and GameOverState"""

from __future__ import annotations
import attrs
import numpy as np
import os
import tcod
import tcod.ecs
import tcod.event
import tcod.constants
import libtcodpy
import g
import game.menus
from game.procgen import generate_dungeon
from game.components import DownStairs,UpStairs,DungeonFloor,Equippable,Experience,Fighter,Gold,Item, Name, Position, Price, MapTiles, MapVisible, MapExplored,FireballDamage
from game.constants import DIRECTION_KEYS
from game.entity_factories import spawn_player
from game.render_functions import render_all
from game.state import Pop,Push,Reset,MultiPop,StateResult
from game.systems import melee_attack, handle_enemy_turns, pick_up_item, drop_item, use_item, resolve_death, toggle_equip_item, save_game, load_game, open_chest, buy_item_from_merchant, sell_item_to_merchant
from game.tags import BlocksMovement, IsItem, IsPlayer, IsActor, IsStairs, IsMap, IsMerchant, IsChest
from tcod.event import KeySym

 ###Menus###
class MainMenu(game.menus.ListMenu):
      """Main/escape menu"""

      __slots__ = ("world",)
      

      def __init__(self,world:tcod.ecs.Registry|None=None) -> None:
        """Initialize main menu"""
        self.world = world if world is not None else tcod.ecs.Registry()

        items = [
            game.menus.SelectItem("New Game",self.new_game), #Make this a self.character_select
            game.menus.SelectItem("Quit",self.quit),
        ]
        has_save_file = os.path.exists("savegame.sav")
        has_active_game = bool(list(self.world.Q.all_of(tags=[IsPlayer, IsActor])))

        if has_active_game or has_save_file:
            items.insert(0,game.menus.SelectItem("Continue",self.continue_))

        super().__init__(
            items=tuple(items),
            selected=0,
            x=5,
            y=5,
        )

#Copy the way the Inventory Menu state makes a list of items then calls on the super() to create a list menu, and add a parameter to new_game to capture character type selected

      def continue_(self) -> StateResult:
          """Load a save file or continue current active session"""
          #Double-check that a player exists to avoid displaying after GameOver
          player_exists = bool(list(self.world.Q.all_of(tags=[IsPlayer],components=[Position])))
          if player_exists:
            return Pop()
          saved_world = load_game()
          if saved_world is not None:
              #saved_player_exists = bool(list(self.world.Q.all_of(tags=[IsPlayer],components=[Position])))
              return Reset(GameplayState(saved_world))
          return self.new_game()
    
      def new_game(self) -> StateResult:
        """Begin a new game with cleared data tables, ignoring any disk saves"""
        if os.path.exists("savegame.sav"):
            try:
                os.remove("savegame.sav")
            except OSError:
                pass
        fresh_world = tcod.ecs.Registry()
        fresh_world[None].components[("MessageLog",list)] = ["Welcome to the Dungeon!"]
        return Reset(GameplayState(fresh_world))
    
      @staticmethod
      def quit() -> StateResult:
        """Close the program"""
        raise SystemExit
      
class InventoryMenuState(game.menus.ListMenu):
    """Interactive overlay panel"""
    __slots__ = ("world","active_map","player","inventory_entities")
    def __init__(self,world:tcod.ecs.Registry,player:tcod.ecs.Entity) -> None:
        self.world = world
        self.player = player
        self.active_map = player.relation_tag["InMap"]
        #Gather player inventory array contents
        all_items = self.world.Q.all_of(tags=[IsItem])
        self.inventory_entities = [item for item in all_items if item.relation_tag.get("InInventoryOf")==self.player or item.relation_tag.get("EquippedIn")==self.player]
        #Build SelectItem list
        menu_items = []
        for item in self.inventory_entities:
            item_name = item.components.get(Name,"Unknown")
            if item.relation_tag.get("EquippedIn") == self.player:
                item_name = f"{item_name} (E)"
            menu_items.append(game.menus.SelectItem(item_name,lambda:None))
        #Initialize ListMenu class with dynamic items
        super().__init__(
            items=tuple(menu_items),
            selected=0,
            x=10,
            y=6
        )
    def drop_selected(self) -> StateResult:
        """Callback function executed when item row activated"""
        if 0 <= self.selected < len(self.inventory_entities):
            item_to_drop = self.inventory_entities[self.selected]
            drop_item(self.world,self.player,item_to_drop)
        #Tick AI clock to make dropping an item take a player turn
            handle_enemy_turns(self.world,self.active_map)
        #Pop back into active gameplay
        return Pop()
    
    def use_selected(self) -> StateResult:
        """Callback function executed when an item row is consumed."""
        if 0 <= self.selected < len(self.inventory_entities):
            item_to_use = self.inventory_entities[self.selected]
            if Equippable in item_to_use.components:
                toggle_equip_item(self.world,self.player,item_to_use)
                handle_enemy_turns(self.world,self.active_map)
                return Pop()
                #Use the item
            did_use = use_item(self.world,self.player,item_to_use)
        #Bring up targeting for ranged items
            if did_use == "needs_target":
                return Push(TargetingOverlayState(self.world,self.player,item_to_use))
        #Enemies take a turn if item was successfully consumed
            elif did_use is True:
                handle_enemy_turns(self.world,self.active_map)
        return Pop()
    
    def check_state_signals(self) -> StateResult:
        """Inspects global registry tags to see if state transition is required."""
        if "TriggerGameOver" in self.world[None].tags:
            self.world[None].tags.remove("TriggerGameOver")
            return Reset(GameOverState(self.world))
        if "TriggerLevelUp" in self.world[None].tags:
            self.world[None].tags.remove("TriggerLevelUp")
            return Push(LevelUpMenuState(self.world,self.player))
        return None
    
    def on_event(self,event:tcod.event.Event) -> StateResult:
        """Intercept key presses or pass standard scrolling to the base class."""
        match event:
            case tcod.event.KeyDown(sym=sym) if sym == KeySym.ESCAPE:
                return Pop()
            case tcod.event.KeyDown(sym=sym) if sym == KeySym.D:
                if self.items:
                    return self.drop_selected()
                return None
            case tcod.event.KeyDown(sym=sym) if sym == KeySym.U:
                if self.items:
                    result = self.use_selected()
                    signal = self.check_state_signals()
                    if signal is not None:
                        return signal
                    return result
                return None
            case tcod.event.KeyDown(sym=sym) if sym in DIRECTION_KEYS:
                dx, dy = DIRECTION_KEYS[sym]
                if dx != 0 or dy == 0:
                    return self.activate_selected(event)
                if self.selected is not None:
                    self.selected += dy
                    self.selected %= len(self.items)
                else:
                    self.selected = 0 if dy == 1 else len(self.items) -1
                return None
            case _:
                #Let the base ListMenu class handle menu navigation
                return super().on_event(event)
            
    def on_draw(self,console:tcod.console.Console) -> None:
        """Draws background game frame beneath ListMenu frame layout"""
        #Maintain background visuals
        render_all(self.world,self.active_map,console,screen_width=80,screen_height=51)
        #Draw decorative UI box window on top
        box_width = 35
        box_height = max(4,len(self.items)+2)
        ix = self.x-2
        iy = self.y-1
        console.draw_rect(x=ix,y=iy,width=box_width,height=box_height,ch=ord(" "),bg=(20,20,20))
        #Call base class draw routine to print text rows and moving highlight bar
        super().on_draw(console)
        console.print(x=ix,y=iy,width=box_width,height=1,text="Inventory (D to Drop)",fg=(255,255,255),bg=(0,0,0),alignment=libtcodpy.CENTER)
        if not self.items:
            console.print(x=self.x,y=self.y+1,text="(Your inventory is completely empty.)", fg=(150,150,150))
            return
        

class LevelUpMenuState(game.menus.ListMenu):
    """Interactive overlay panel forcing character trait selections on level up."""
    __slots__ = ("world","active_map","player")

    def __init__(self,world:tcod.ecs.Registry,player:tcod.ecs.Entity) -> None:
        self.world = world
        self.player = player
        self.active_map = player.relation_tag["InMap"]

        menu_items = [
            game.menus.SelectItem("Constitution (+20 Max HP)",self.raise_hp),
            game.menus.SelectItem("Strength (+1 Power)",self.raise_power),
            game.menus.SelectItem("Agility (+1 Defense)",self.raise_defense),
        ]
        #if player.level > 5
        #menu_items.append better bonuses to menu for higher levels later

        super().__init__(
            items=tuple(menu_items),
            selected=0,
            x=15,
            y=10
        )
    def process_level_advancement(self) -> None:
        """Advances level numbers and updates the next required threshold."""
        log = self.world[None].components[("MessageLog",list)]
        xp_tracker = self.player.components[Experience]
        fighter = self.player.components[Fighter]
        xp_tracker.current_xp -= xp_tracker.xp_to_next_level
        xp_tracker.level += 1
        #Scaling threshold
        xp_tracker.xp_to_next_level += 150
        fighter.hp = fighter.max_hp
        lvl_up_msg = f"You have reached level {xp_tracker.level}!"
        log.append(lvl_up_msg)
    def raise_hp(self) -> StateResult:
        fighter = self.player.components[Fighter]
        fighter.max_hp += 20
        self.process_level_advancement()
        return Pop()
    def raise_power(self) -> StateResult:
        fighter = self.player.components[Fighter]
        fighter.power += 1
        self.process_level_advancement()
        return Pop()
    def raise_defense(self) -> StateResult:
        fighter = self.player.components[Fighter]
        fighter.defense += 1
        self.process_level_advancement()
        return Pop()
    #def add_ability -> for adding a special ability, will need to redirect to a new menu to assign a button to the ability
    #def add_mana -> for adding mana to a magic-users' current pool
    def on_event(self,event:tcod.event.Event) -> StateResult:
        match event:
            case tcod.event.Quit():
                raise SystemExit
            case tcod.event.KeyDown(sym=sym) if sym == KeySym.RETURN:
                if self.items:
                    selected_item = self.items[self.selected]
                    command = selected_item.callback()
                    return command
                return None
            case _:
                return super().on_event(event)
    def on_draw(self,console:tcod.console.Console) -> None:
        render_all(self.world,self.active_map,console,screen_width=80,screen_height=51)
        box_width = 40
        box_height = 6
        bx = self.x-2
        by = self.y-1
        console.draw_rect(x=bx,y=by,width=box_width,height=box_height,ch=ord(" "),bg=(30,20,20))
        
        #console.draw_frame(x=bx,y=by,width=box_width,height=box_height,fg=(255,215,0))
        super().on_draw(console)
        console.print(x=0, y=3, width=None, height=1, string="LEVEL UP /n Select an Attribute", alignment=tcod.constants.CENTER)
        

class ShopMenuState(game.menus.ListMenu):
    """Interactive storefront handling buying and selling loops."""
    __slots__ = ("world","active_map","player","merchant","is_sell_mode","shop_entities")
    def __init__(self,world:tcod.ecs.Registry,player:tcod.ecs.Entity,merchant:tcod.ecs.Entity) -> None:
        self.world=world
        self.player=player
        self.merchant=merchant
        self.active_map=player.relation_tag["InMap"]
        self.is_sell_mode=False #Starts on Buy mode by default
        self.refresh_menu_items()
    def get_current_pool(self) -> list[tcod.ecs.Entity]:
        """Queries database tracking tokens based on buying and selling filters."""
        all_items=self.world.Q.all_of(tags=["IsItem"])
        if self.is_sell_mode:
            return [i for i in all_items if i.relation_tag.get("InInventoryOf") == self.player or i.relation_tag.get("EquippedIn") == self.player]
        else:
            return [i for i in all_items if i.relation_tag.get("InInventoryOf") == self.merchant]
    def refresh_menu_items(self) -> None:
        """Dynamically builds choice arrays matching active shop mode configurations."""
        self.shop_entities = self.get_current_pool()
        menu_items = []
        for item in self.shop_entities:
            raw_name = item.components.get(Name)
            if self.is_sell_mode:
                base_val = item.components[Price].value if Price in item.components else 30
                cost_string = f"{raw_name}(+{max(5,base_val//2)}g)"
            else:
                cost = item.components[Price].value if Price in item.components else 25
                cost_string = f"{raw_name} ({cost}g)"
            menu_items.append(game.menus.SelectItem(cost_string, self.execute_transaction))
        if hasattr(self, "items"):
            self.items = tuple(menu_items)
            self.selected = max(0,min(self.selected,len(menu_items)-1))
        else:
            super().__init__(
                items=tuple(menu_items),
                selected=self.clamp(self.selected,0,(max(0,len(menu_items)-1))) if hasattr(self,"selected") else 0,
                x=10,
                y=6
            )
    def execute_transaction(self) -> StateResult:
        """Triggers transactional operations when rows are activated."""
        if 0 <= self.selected < len(self.shop_entities):
            target_item = self.shop_entities[self.selected]
            if self.is_sell_mode:
                sell_item_to_merchant(self.world,self.player,self.merchant,target_item)
            else:
                buy_item_from_merchant(self.world,self.player,self.merchant,target_item)
            self.refresh_menu_items()
        return None
    def on_event(self,event:tcod.event.Event) -> StateResult:
        match event:
            case tcod.event.KeyDown(sym=sym) if sym == KeySym.ESCAPE:
                return Pop()
            case tcod.event.KeyDown(sym=sym) if sym == KeySym.TAB:
                #Toggle between Buy and Sell panels
                self.is_sell_mode = not self.is_sell_mode
                self.selected = 0
                self.refresh_menu_items()
                return None
            case tcod.event.KeyDown(sym=sym) if sym == KeySym.RETURN:
                if self.items:
                    return self.execute_transaction()
                return None
            case _:
                return super().on_event(event)
    def on_draw(self,console:tcod.console.Console) -> None:
        render_all(self.world,self.active_map,console,screen_width=80,screen_height=51)
        box_width = 45
        box_height = max(5,len(self.items)+3)
        title_text = "SHOP: SELL MODE" if self.is_sell_mode else "SHOP: BUY MODE"
        #bottom_text = "TAB to change mode"
        
        console.draw_rect(x=self.x-2,y=self.y-1,width=box_width,height=box_height,ch=ord(" "),bg=(20,20,30))
        
        #console.draw_frame(x=self.x-2,y=self.y-1,width=box_width,height=box_height,fg=(255,192,203),bg=(20,20,30))
        super().on_draw(console)
        console.print(x=box_width//2,y=self.y-1,width=15,height=1,string=title_text,fg=(255,255,255),bg=(20,20,30),alignment=libtcodpy.CENTER)
        #console.print(x=box_width//2,y=box_height+3,width=20,height=1,string=bottom_text,alignment=libtcodpy.CENTER)
        player_gold = self.player.components.get(Gold,0)
        console.print(x=self.x,y=box_height+10,width=None,height=1,string=f"Your Gold: {player_gold}g",fg=(255,255,0),alignment=libtcodpy.LEFT)
        if not self.items:
            console.print(x=self.x,y=self.y+1,width=None,height=1,string="(No items available)",fg=(150,150,150),alignment=libtcodpy.CENTER)
            return
        
    @staticmethod
    def clamp(val:int,min_v:int, max_v:int) -> int: 
        return max(min_v, min(val, max_v))


###Game States###
class GameplayState:
    def __init__(self,world:tcod.ecs.Registry) -> None:
        self.world=world
        existing_maps = list(self.world.Q.all_of(tags=[IsMap]))
        if existing_maps:
            self.active_map = existing_maps[0]
            self.player = list(self.world.Q.all_of(tags=[IsPlayer]))[0]
            if Position in self.player.components:
                player_pos = self.player.components[Position]
        else:
            self.active_map, self.player_start = generate_dungeon(
                world=self.world,
                map_width=80,
                map_height=45,
                max_rooms=30,
                room_min_size=6,
                room_max_size=10,
                floor_number=1
                )
            start_x, start_y = self.player_start
            player_pos = Position(x=start_x,y=start_y)
            self.player=spawn_player(self.world,player_pos)
            self.player.components[Gold] = 0
                    
        self.player.components[Position] = player_pos
        self.player.tags.add(player_pos)
        self.player.relation_tag["InMap"] = self.active_map
        #Initial FOV calculation when entering the level
        self.update_fov()

    def update_fov(self) -> None:
        """Computes the player's line of sight and logs explored map sectors"""
        tiles=self.active_map.components[MapTiles]
        player_pos=self.player.components[Position]

        #1 Create a boolean transparency map: anything that isn't a wall ('#')
        transparency = tiles["ch"] != ord("#")

        #2 Compute visibility grid array using libtcod's shadowcasting
        #Note: compute_fov takes a 2D array and a 2-item (y,x) or (x,y) index matched to the array
        #Because NumPy is structured as [y,x], we pass the coordinate tuple following this structure
        visible_mask=tcod.map.compute_fov(
            transparency=transparency,
            pov=(player_pos.y,player_pos.x),
            radius=8,
            light_walls=True,
            algorithm=tcod.constants.FOV_SHADOW
        )

        #3 Commit the evaluated mask directly back into the map entity components
        self.active_map.components[MapVisible]=visible_mask

        #4 Use a bitwise OR |= to persistently record rooms the player has unveiled
        self.active_map.components[MapExplored] |= visible_mask
    
    def check_state_signals(self) -> StateResult:
        """Inspects global registry tags to see if state transition is required."""
        if "TriggerGameOver" in self.world[None].tags:
            self.world[None].tags.remove("TriggerGameOver")
            return Reset(GameOverState(self.world))
        if "TriggerLevelUp" in self.world[None].tags:
            self.world[None].tags.remove("TriggerLevelUp")
            return Push(LevelUpMenuState(self.world,self.player))
        return None

    def on_event(self,event:tcod.event.Event) -> None:
        """Handle events for in-game state."""
        
        player_query=list(self.world.Q.all_of(tags=[IsPlayer]))
        if not player_query:
            return None
        player = player_query[0]
        player_pos = player.components[Position]
        player.tags.add(player_pos)
        log = self.world[None].components[("MessageLog",list)]
        match event:
            case tcod.event.Quit():
                raise SystemExit
            case tcod.event.KeyDown(sym=sym) if sym in DIRECTION_KEYS:
                #This should be made into its own function player_turn 
                dx,dy=DIRECTION_KEYS[sym]
                target_pos=Position(x=player_pos.x+dx,y=player_pos.y+dy)
                tiles=self.active_map.components[MapTiles]
                if 0 <= target_pos.x < tiles.shape[1] and 0<= target_pos.y < tiles.shape[0]:
                    #Fetch tile at target coordinate (Note, numpy arrays are [y,x]) and check to see if it's a wall
                    target_tile = tiles[target_pos.y,target_pos.x]
                    if target_tile["ch"]==ord("#"):
                        block_msg ="The way is blocked by a solid wall."
                        log.append(block_msg)
                        return None
                    blocking_entities = list(
                        self.world.Q.all_of(tags=[target_pos,BlocksMovement])
                    )
                    if blocking_entities:
                        target_entity = blocking_entities[0]
                        if IsMerchant in target_entity.tags:
                            return Push(ShopMenuState(self.world,player,target_entity))
                        if IsChest in target_entity.tags:
                            open_chest(self.world,target_entity)
                            handle_enemy_turns(self.world,self.active_map)
                            return None
                        #Intercept any game over returns
                        result = melee_attack(self.world, player, target_entity)
                        if result is not None:
                            return result
                        #Enemy turns
                        result = handle_enemy_turns(self.world,self.active_map)
                        if result is not None:
                            return result
                        return None
                    else:
                        player.tags.remove(player_pos)
                        player.components[Position] = target_pos
                        player.tags.add(target_pos)
                        self.update_fov()
                #Auto pickup gold - could be made into its own function?
                    for gold in list(self.world.Q.all_of(components=[Gold], tags=[target_pos,IsItem])):
                        player.components[Gold] += gold.components[Gold]
                        gold_msg = f"Picked up {gold.components[Gold]}g"
                        log.append(gold_msg)
                        gold.clear()
                    #Trigger enemy turns
                    handle_enemy_turns(self.world, self.active_map)
                    signal = self.check_state_signals()
                    if signal is not None:
                        return signal
                    save_game(self.world)
                    return None
                else:
                    #Target position is outside the boundaries of the grid array
                    oob_msg= f"You cannot move beyond the boundaries of the map."
                    log.append(oob_msg)
                return None
            case tcod.event.KeyDown(sym=KeySym.ESCAPE):
                return Push(MainMenu(world=self.world))
            case tcod.event.KeyDown(sym=sym) if sym == KeySym.KP_ENTER or sym == KeySym.PERIOD:
                #Should also be made into its own function go_downstairs
                if not player_query:
                    return None
                #Query for stairs on the player's coordinates
                stairs_query = list(
                    self.world.Q.all_of(tags=[player_pos,IsStairs],components=[DownStairs])
                )
                if stairs_query:
                    dwnstr_msg = f"You descend deeper into the darkness of the dungeon."
                    log.append(dwnstr_msg)
                    current_floor = self.active_map.components.get(DungeonFloor)
                    next_floor_level = current_floor.level+1 if current_floor else 2
                    #Generate a new level map - this is generating a new level if you go up then back down!
                    new_map,new_player_start = generate_dungeon(
                        world=self.world,
                        map_width=80,
                        map_height=45,
                        max_rooms=30,
                        room_min_size=6,
                        room_max_size=10,
                        floor_number=next_floor_level
                    )
                    new_map.relation_tag["AboveMap"] = self.active_map
                    #Update player position
                    player.tags.remove(player_pos)
                    start_x,start_y = new_player_start
                    new_pos = Position(x=start_x,y=start_y)
                    player.components[Position] = new_pos
                    player.tags.add(new_pos)
                    #Point player relationship tag to new map
                    player.relation_tag["InMap"] = new_map
                    #Swap active state context and refresh FOV
                    self.active_map = new_map
                    self.update_fov()
                else:
                    no_stairs_msg = f"There are no staircases here to descend."
                    log.append(no_stairs_msg)
                return None
            case tcod.event.KeyDown(sym=sym) if sym == KeySym.COMMA or sym == KeySym.BACKSPACE:
                #Make its own function go_upstairs
                if not player_query:
                    return None
                up_stairs_query = list(self.world.Q.all_of(tags=[player_pos,IsStairs],components=[UpStairs]))
                if up_stairs_query:
                    above_map_entity = self.active_map.relation_tag.get("AboveMap")
                    if above_map_entity is not None:
                        upstr_msg = f"You climb back up the staircase to the previous floor."
                        log.append(upstr_msg)
                        upper_stairs = [
                            s for s in self.world.Q.all_of(tags=[IsStairs], components=[Position])
                            if s.relation_tag.get("InMap") == above_map_entity
                        ]
                        if upper_stairs:
                            arrival_pos = upper_stairs[0].components[Position]
                        else:
                            arrival_pos = Position(x=10,y=10)
                        player.tags.remove(player_pos)
                        player.components[Position] = arrival_pos
                        player.tags.add(arrival_pos)
                        player.relation_tag["InMap"] = above_map_entity
                        self.active_map = above_map_entity
                        self.update_fov()
                        save_game(self.world)
                    else:
                        first_floor_msg = "You are already on the highest floor of the dungeon."
                        log.append(first_floor_msg)
                else:
                    no_ustairs_msg = "There is no upward staircase here to climb."
                    log.append(no_ustairs_msg)
                return None
            case tcod.event.KeyDown(sym=sym) if sym == KeySym.G:
                #Trigger player item collection
                pick_up_item(self.world,self.player)
                #Progress game turn clock
                handle_enemy_turns(self.world,self.active_map)
                return None
            case tcod.event.KeyDown(sym=sym) if sym == KeySym.I:
                return Push(InventoryMenuState(self.world,self.player))
            case _:
                return None

    def on_draw(self,console:tcod.console.Console) -> None:
        render_all(
            world=self.world,
            active_map=self.active_map,
            root_console=console,
            screen_width=80,
            screen_height=50
        )
        g.context.present(console)

class GameOverState:
    """State activated when the player dies. Disable movement controls completely"""

    __slots__ = ("world", "active_map")

    def __init__(self,world:tcod.ecs.Registry) -> None:
        self.world = world
        #Find current active map entity
        self.active_map = next(iter(self.world.Q.all_of(tags=[IsMap])))

    def on_event(self,event:tcod.event.Event) -> StateResult:
        """Only permits escaping back to the main menu system"""
        match event:
            case tcod.event.Quit():
                raise SystemExit
            case tcod.event.KeyDown(sym=sym) if sym == KeySym.ESCAPE:
                #Send back a fresh main menu context
                g.states = [MainMenu(world=self.world)]
                return None
            case _:
                return None
            
    def on_draw(self,console:tcod.console.Console) -> None:
        """Renders the screen frame with a frozen player asset and a visual overlay."""
        #1 Draw game screen using our rendering infrastructure
        render_all(
                   world=self.world,
                   active_map=self.active_map,
                   root_console=console,
                   screen_width=80,
                   screen_height=51
                   )
        #2 Paint a dramatic game over message panel overlay
        center_x = (console.width//2)-15
        center_y = (console.height//2)-2

        console.print(
            x=center_x,
            y=center_y,
            width=30,
            height=4,
            text="=== GAME OVER ===\n\nPress ESC for Main Menu",
            fg=(255,0,0),
            bg=(0,0,0),
            alignment=tcod.constants.CENTER
        )

class TargetingOverlayState:
    """An interactive cursor targeting system overlay."""
    __slots__ = ("world","active_map","player","item","cursor_x","cursor_y")
    
    def __init__(self, world: tcod.ecs.Registry, player: tcod.ecs.Entity, item:tcod.ecs.Entity) -> None:
        self.world=world
        self.player=player
        self.active_map=player.relation_tag["InMap"]
        self.item=item
        #Default crosshair targeting coordinate at player position
        p_pos = player.components[Position]
        self.cursor_x = p_pos.x
        self.cursor_y = p_pos.y
    
    def on_event(self, event: tcod.event.Event) -> StateResult:
        log = self.world[None].components[("MessageLog",list)]
        match event:
            case tcod.event.Quit():
                raise SystemExit
            case tcod.event.KeyDown(sym=sym) if sym in DIRECTION_KEYS:
                dx, dy = DIRECTION_KEYS[sym]
                self.cursor_x += dx
                self.cursor_y += dy
                return None
            case tcod.event.KeyDown(sym=sym) if sym == KeySym.ESCAPE:
                cncl_msg = f"Targeting canceled."
                log.append(cncl_msg)
                return Pop()
            case tcod.event.KeyDown(sym=sym) if sym == KeySym.KP_ENTER or sym == KeySym.RETURN:
                #Confirm coordinate target
                visible_mask = self.active_map.components[MapVisible]
                #Can't target something out of sight
                if not visible_mask[self.cursor_y,self.cursor_x]:
                    cannot_target_msg = f"You cannot target an area that you cannot actively see."
                    log.append(cannot_target_msg)
                    return None
                fdamage = self.item.components.get(FireballDamage)
                if fdamage:
                    fireball = fdamage
                    fball_msg = f"The fireball detonates at ({self.cursor_x},{self.cursor_y}) in a burst of fire!"
                    log.append(fball_msg)
                    self.item.clear()
                    #Query active fighters on current map layer
                    entities = self.world.Q.all_of(components=[Position,Fighter])
                    for entity in list(entities):
                        #Skip entities from other map levels, unless it's the player (?)
                        if entity.relation_tag.get("InMap") != self.active_map and IsPlayer not in entity.tags:
                            continue
                        pos = entity.components[Position]
                        #Calculate distance from blast center
                        dist = max(abs(pos.x-self.cursor_x),abs(pos.y-self.cursor_y))
                        if dist <= fireball.radius:
                            fighter = entity.components[Fighter]
                            fighter.hp -= fireball.damage
                            #Bring up name for message log
                            fighter_name = entity.components[Name]
                            fball_dmg_msg = f"The blast engulfs {fighter_name}, dealing {fireball.damage} damage!"
                            log.append(fball_dmg_msg)
                            if fighter.hp <= 0:
                                death_result = resolve_death(self.world,entity,fighter_name)
                                if death_result is not None:
                                    return death_result        
                    self.item.clear()
                    handle_enemy_turns(self.world,self.active_map)
                return MultiPop(count=2)
            
    def on_draw(self,console:tcod.console.Console) -> None:
        render_all(
            world=self.world,
            active_map=self.active_map,
            root_console=console,
            screen_width=80,
            screen_height=51
        )
        if 0 <= self.cursor_x < console.width and 0 <= self.cursor_y < console.height:
            console.print(x=self.cursor_x, y=self.cursor_y, text="*", fg=(0, 255, 255), bg=(0, 100, 100))