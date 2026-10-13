"""Contains enemy turn system, melee attack system, game over system, and item pickup."""

import numpy as np
import os
import pickle
import random
import tcod.ecs
from game.components import AbilityType, AbilityData, Chest,Equippable, Experience, ExperienceBounty, Fighter, Gold, Graphic, Heal, Item, LootTable,Name, Position, Price, MapTiles, MapVisible, LightningDamage, ChainLightningDamage,FireballDamage
from game.tags import BlocksMovement,IsItem,IsPlayer,IsActor
from game import entity_factories

SAVE_FILE = "savegame.sav"

def save_game(world: tcod.ecs.Registry) -> None:
    """Serialize entire global ECS world into a binary file"""
    try:
        with open(SAVE_FILE,"wb") as f:
            pickle.dump(world,f)
    except Exception as e:
        #Print to prevent crash if filesystem error happens
        print(f"Error saving game data: {e}")

def load_game() -> tcod.ecs.Registry | None:
    """Deserializes and reconstructs global ECS world from binary file on disk"""
    try:
        with open(SAVE_FILE,"rb") as f:
            world = pickle.load(f)
        return world
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"Error loading save data: {e}")
        return None

def handle_enemy_turns(world:tcod.ecs.Registry,active_map:tcod.ecs.Entity) -> None:
    """System that queries living monsters and moves them towards the player"""
    #1 Fetch player's position
    player_query = list(world.Q.all_of(tags=[IsPlayer]))
    if not player_query:
        return
    player=player_query[0]
    player_pos=player.components[Position]
    #2 Extract map tiles and visibility mask
    tiles = active_map.components[MapTiles]
    visible_mask = active_map.components[MapVisible]

    #Create cost map for pathfinding (0=blocked/wall, 1=walkable floor)
    #tcod.path expects a 2d array where 0 is blocked and values > 0 are walkable

    walkable_cost = np.where(tiles["ch"] != ord("#"),1,0).astype(np.int32)

    #3 Query all non-player living actors linked to this map
    #Filter out the "IsPlayer" tag so enemies don't process themselves
    monsters = world.Q.all_of(
        tags=[IsActor],
        components=[Position]
        ).none_of(tags=[IsPlayer])
    
    for monster in monsters:
        #Check if monster belongs to current map floor
        if monster.relation_tag.get("InMap") != active_map:
            continue
        monster_pos = monster.components[Position]
        #Monsters will only wake up when the player can see them
        if not visible_mask[monster_pos.y,monster_pos.x]:
            continue
        #Calculate distance to player
        dx = player_pos.x-monster_pos.x
        dy = player_pos.y-monster_pos.y
        distance = max(abs(dx),abs(dy))
        #If the enemy is right next to the player, they attack
        if distance <= 1:
            result = melee_attack(world,monster,player)
            if result is not None:
                return result #If a Game Over, stops processing other monster turns
            continue
        #Otherwise, find a step towards the player using HillClimbing pathfinding (finds fastest path on 2d cost grid)
        pathfinder = tcod.path.AStar(cost=walkable_cost,diagonal=1.41)
        #get_path returns a list of coordinates from start to goal: [(x,y),(x2,y2),...]
        path = pathfinder.get_path(
            start_x=monster_pos.y,
            start_y=monster_pos.x,
            goal_x=player_pos.y,
            goal_y=player_pos.x
        )

        if path:
            #path[0] gives the next step as a (y,x) coordinate tuple
            next_y, next_x = path[0]
            target_pos = Position(x=next_x,y=next_y)
            #Ensure next step isn't blocked by another enemy
            blocking_query = list(world.Q.all_of(tags=[target_pos,BlocksMovement]))
            if not blocking_query:
                #safely update the monster's spatial components and tags
                monster.tags.remove(monster_pos)
                monster.components[Position] = target_pos
                monster.tags.add(target_pos)
        if list(world.Q.all_of(tags=[monster_pos,IsItem])):
            pick_up_item(world,monster)
            continue

def get_total_power(world:tcod.ecs.Registry,entity:tcod.ecs.Entity) -> int:
    fighter = entity.components.get(Fighter)
    base_power = fighter.power if fighter is not None else 0
    bonus = 0
    #Query any items equipped by the entity
    equipped_items = [e for e in world.Q.all_of(components=[Equippable]) if e.relation_tag.get("EquippedIn") == entity]
    for item in equipped_items:
        bonus += item.components[Equippable].power_bonus
    return base_power+bonus

def get_total_defense(world:tcod.ecs.Registry,entity:tcod.ecs.Entity) -> int:
    fighter = entity.components.get(Fighter)
    base_defense = fighter.defense if fighter is not None else 0
    bonus = 0
    equipped_items = [e for e in world.Q.all_of(components=[Equippable]) if e.relation_tag.get("EquippedIn") == entity]
    for item in equipped_items:
        bonus += item.components[Equippable].defense_bonus
    return base_defense + bonus

def melee_attack(world: tcod.ecs.Registry, attacker: tcod.ecs.Entity, defender: tcod.ecs.Entity) -> None:
    """Evaluates combat math and resolves damage distribution between entities"""
    if Fighter not in attacker.components or Fighter not in defender.components:
        return
    
    total_power = get_total_power(world,attacker)
    total_defense = get_total_defense(world,defender)

    defender_fighter = defender.components.get(Fighter)

    #calculate damage - everyone is doing a flat damage number right now, I want to randomize this a little
    #if IsPlayer in attacker.tags or defender.tags:
    damage = total_power - total_defense
    #else: damage = random.randint(0,attacker_fighter.power) - defender_fighter.defense

    attacker_name = attacker.components.get(Name,"Unknown")
    defender_name = defender.components.get(Name,"Unknown")

    log = world[None].components[("MessageLog",list)]

    if damage > 0:
        defender_fighter.hp -= damage
        damage_msg = f"{attacker_name} attacks {defender_name} for {damage} hit points!"
        log.append(damage_msg)
        #Check for death conditions
        if defender_fighter.hp <= 0:
            return resolve_death(world, defender, defender_name)
    else:
        no_dmg_msg = f"{attacker_name} attacks {defender_name} but does no damage."
        log.append(no_dmg_msg)
    return None

def resolve_death(world: tcod.ecs.Registry, entity: tcod.ecs.Entity, name: str) -> None:
    """Transforms living actor into flat corpse"""
    log = world[None].components[("MessageLog", list)]
    if IsPlayer not in entity.tags:
        death_msg = f"The {name} has died!"
        log.append(death_msg)
        drop_monster_equipment(world,entity)
        drop_monster_loot(world,entity)
        entity.tags.remove(IsActor)
        entity.tags.remove(BlocksMovement)

    if IsPlayer in entity.tags:
        you_died_msg = f"Game Over! You died."
        log.append(you_died_msg)
        entity.components[Graphic] = Graphic(ch=ord("%"),fg=(150,0,0))
        #Permadeath like all good roguelikes
        if os.path.exists(SAVE_FILE):
            try:
                os.remove(SAVE_FILE)
            except OSError:
                pass
        world[None].tags.add("TriggerGameOver")
        return    
    if ExperienceBounty in entity.components:
        bounty = entity.components[ExperienceBounty]
        player_query = list(world.Q.all_of(tags=[IsPlayer],components=[Experience]))
        if player_query:
            player = player_query[0]
            xp_tracker = player.components[Experience]
            xp_tracker.current_xp += bounty.amount
            xp_msg = f"You gain {bounty.amount} experience points."
            log.append(xp_msg)
            if xp_tracker.current_xp >= xp_tracker.xp_to_next_level:
                lvl_up_msg = f"You have leveled up!"
                log.append(lvl_up_msg)
                world[None].tags.add("TriggerLevelUp")
    
    if Graphic in entity.components:
        entity.components[Graphic] = Graphic(ch=ord("%"),fg=(191,0,0))
    return None

def pick_up_item(world:tcod.ecs.Registry,actor:tcod.ecs.Entity) -> None:
    """Moves an item from the floor at the actor's feet into their inventory"""
    if Position not in actor.components:
        return
    actor_pos = actor.components[Position]
    log = world[None].components[("MessageLog",list)]
    #Query for pickable items at the actor's exact spatial position tag
    items_at_feet = list(world.Q.all_of(tags=[actor_pos,IsItem],components=[Item]))
    if not items_at_feet:
        no_pickup_msg = f"There is nothing here to pick up."
        log.append(no_pickup_msg)
        return
    target_item = items_at_feet[0]
    item_name = target_item.components.get(Name,"Unknown")
    actor_name = actor.components.get(Name,"Unknown")
    #Remove coordinates so item disappears from map
    target_item.tags.remove(actor_pos)
    del target_item.components[Position]
    if "InMap" in target_item.relation_tag:
        del target_item.relation_tag["InMap"]
    #Bind item to actor using child-owner relationship tag
    target_item.relation_tag["InInventoryOf"] = actor
    pickup_msg = f"{actor_name} picked up the {item_name}."
    log.append(pickup_msg)

def drop_item(world:tcod.ecs.Registry,actor:tcod.ecs.Entity,item:tcod.ecs.Entity) -> None:
    """Detaches an item from the actor's inventory and places it back onto the floor map."""
    actor_pos = actor.components[Position]
    active_map = actor.relation_tag["InMap"]
    log = world[None].components[("MessageLog",list)]
    item_name = item.components.get(Name,"Unknown")
    actor_name = actor.components.get(Name,"Unknown")
    #Break inventory ownership link
    del item.relation_tag["InInventoryOf"]
    #Apply physical map attributes and tie back to active level floor
    item.components[Position] = actor_pos
    item.tags.add(actor_pos)
    item.relation_tag["InMap"] = active_map
    drop_msg = f"{actor_name} dropped the {item_name}."
    log.append(drop_msg)

def use_item(world:tcod.ecs.Registry,actor:tcod.ecs.Entity,item:tcod.ecs.Entity) -> bool:
    """"Consumes an item from inventory, applies its effects, and returns True if successful."""
    log = world[None].components[("MessageLog",list)]
    item_name = item.components.get(Name,"Unknown")
    actor_name = actor.components.get(Name,"Unknown")
    #Check that non-fighters cannot use consumables
    if Fighter not in actor.components:
        cnsm_fail_msg = f"{actor_name} cannot use {item_name}."
        log.append(cnsm_fail_msg)
        return False        
    #Healing potion resolution - make into a function
    if Heal in item.components:
        if Fighter not in actor.components: return False
        fighter = actor.components[Fighter]
        if fighter.hp >= fighter.max_hp:
            full_msg = f"{actor_name}'s health is already full!"
            log.append(full_msg)
            return False
        heal_effect = item.components[Heal]
        #Calculate how much health is recovered before hitting max amount
        amount_healed = min(fighter.max_hp-fighter.hp, heal_effect.amount)
        fighter.hp += amount_healed
        heal_msg = f"{actor_name} used the {item_name}, recovering {amount_healed} HP!"
        log.append(heal_msg)
        #Remove item from inventory/world
        item.clear()
        return True
    #Lightning scroll resolution - make into a function
    if LightningDamage in item.components:
        effect = item.components[LightningDamage]
        actor_pos = actor.components[Position]
        active_map = actor.relation_tag["InMap"]
        visible_mask = active_map.components[MapVisible]
        #Query visible monsters
        monsters = world.Q.all_of(tags=[IsActor],components=[Position]).none_of(tags=[IsPlayer])
        closest_target = None
        closest_dist = effect.max_range +1
        for monster in monsters:
            if monster.relation_tag.get("InMap") != active_map: continue
            m_pos = monster.components[Position]
            if not visible_mask[m_pos.y,m_pos.x]: continue
            #Distance check
            dist = max(abs(m_pos.x-actor_pos.x),abs(m_pos.y-actor_pos.y))
            if dist < closest_dist:
                closest_dist = dist
                closest_target = monster
        if closest_target:
            m_fighter = closest_target.components.get(Fighter)
            m_name = closest_target.components.get(Name)
            if m_fighter:
                m_fighter.hp -= effect.damage
                target = m_name
                lbolt_msg = f"A lightning bolt strikes {target} for {effect.damage} damage!"
                log.append(lbolt_msg)
                if m_fighter.hp <= 0:
                    resolve_death(world,closest_target,target)
                item.clear()
                return True
        no_lghtng_trgt_msg = f"There are no enemies nearby to strike with lightning."
        log.append(no_lghtng_trgt_msg)
        return False
    #Chain Lightning scroll resolution - make into a function
    if ChainLightningDamage in item.components:
        effect = item.components[ChainLightningDamage]
        active_map = actor.relation_tag["InMap"]
        visible_mask = active_map.components[MapVisible]
        current_source_pos = actor.components[Position]
        struck_entities = set()
        jumps_made = 0
        monsters = world.Q.all_of(tags=[IsActor],components=[Position]).none_of(tags=[IsPlayer])
        available_targets = [m for m in monsters if m.relation_tag.get("InMap") == active_map]
        while jumps_made < effect.max_jumps:
            closest_target = None
            closest_dist = effect.max_range+1
            for monster in available_targets:
                if monster in struck_entities:
                    continue
                m_pos = monster.components[Position]
                if jumps_made == 0 and not visible_mask[m_pos.y,m_pos.x]:
                    continue
                dist = max(abs(m_pos.x-current_source_pos.x),abs(m_pos.y-current_source_pos.y))
                if dist < closest_dist:
                    closest_dist = dist
                    closest_target = monster
            if closest_target:
                m_fighter = closest_target.components.get(Fighter)
                m_name = closest_target.components.get(Name)
                if m_fighter:
                    m_fighter.hp -= effect.damage
                    if jumps_made == 0:
                        cast_cl_msg = f"A bolt of lightning arcs from {actor_name}'s fingers to the {m_name} for {effect.damage} damage!"
                        log.append(cast_cl_msg)
                    else:
                        cl_arc_msg = f"The bolt arcs into a nearby {m_name} for {effect.damage} damage!"
                        log.append(cl_arc_msg)
                    if m_fighter.hp <= 0:
                        resolve_death(world,closest_target,m_name)
                struck_entities.add(closest_target)
                current_source_pos = closest_target.components[Position]
                jumps_made += 1
            else:
                break
        if jumps_made > 0:
            item.clear()
            return True
        no_cl_trgt_msg = f"There are no enemies nearby to strike with chain lightning."
        log.append(no_cl_trgt_msg)
        return False
        
    #Fireball scroll passes to targeting overlay - leave this one be for now
    if FireballDamage in item.components:
        return "needs_target"
    else:
        no_effect_msg = f"This item has no usable effect."
        log.append(no_effect_msg)
        return False

def get_equipped_item(world:tcod.ecs.Registry,actor:tcod.ecs.Entity,slot:any) -> tcod.ecs.Entity | None:
    """Queries what item is actively equipped in a specific slot"""
    items = world.Q.all_of(components=[Equippable])
    for item in items:
        if item.relation_tag.get("EquippedIn") == actor:
            if item.components[Equippable].slot == slot:
                return item
    return None

def toggle_equip_item(world:tcod.ecs.Registry,actor:tcod.ecs.Entity,item:tcod.ecs.Entity) -> None:
    """Swaps an item between inventory and active equipment slots."""
    log = world[None].components[("MessageLog",list)]
    if Equippable not in item.components:
        non_equip_msg = f"This item cannot be equipped."
        log.append(non_equip_msg)
        return
    item_equip = item.components[Equippable]
    item_name = item.components[Name]

    #Un-equip item and send back to inventory
    if item.relation_tag.get("EquippedIn") == actor:
        equip_name = item.components[Name]
        del item.relation_tag["EquippedIn"]
        item.relation_tag["InInventoryOf"] = actor
        unequip_msg = f"You un-equip the {equip_name}."
        log.append(unequip_msg)
    
    #Equip item from inventory menu - automatically un-equips anything in that slot
    current_equip = get_equipped_item(world,actor,item_equip.slot)
    if current_equip:
        equip_name = current_equip.components.get[Name]
        del current_equip.relation_tag["EquippedIn"]
        current_equip.relation_tag["InInventoryOf"] = actor
        log.append(unequip_msg)
    if "InInventoryOf" in item.relation_tag:
        del item.relation_tag["InInventoryOf"]
    item.relation_tag["EquippedIn"] = actor
    equip_msg = f"You equip the {item_name}."
    log.append(equip_msg)

def open_chest(world:tcod.ecs.Registry,chest_entity:tcod.ecs.Entity) -> None:
    chest_data = chest_entity.components.get(Chest)
    if not chest_data or chest_data.is_open:
        return
    log = world[None].components[("MessageLog",list)]
    pos = chest_entity.components[Position]
    active_map = chest_entity.relation_tag["InMap"]
    chest_data.is_open = True
    chest_entity.tags.remove(BlocksMovement)
    chest_entity.components[Graphic] = Graphic(ch=ord("\\"),fg=(139,69,19))
    open_msg = "You open the treasure chest!"
    log.append(open_msg)
    loot_pool = [
        entity_factories.spawn_gold,
        entity_factories.spawn_healing_potion,
        entity_factories.spawn_lightning_scroll,
        entity_factories.spawn_fireball_scroll,
        entity_factories.spawn_chain_lightning_scroll
    ] #Change this later to use the LootPool component and change the odds of dropping something
    num_drops = random.randint(1,2)
    for _ in range(num_drops):
        factory = random.choice(loot_pool)
        dropped_item = factory(world,active_map,pos)
        dropped_item.components[Position] = pos
        dropped_item.tags.add(pos)
        dropped_item.tags.add(IsItem)
        dropped_item.relation_tag["InMap"] = active_map
    loot_msg = "Items spill out onto the ground!"
    log.append(loot_msg)

def drop_monster_loot(world: tcod.ecs.Registry,monster_entity:tcod.ecs.Entity) -> None:
    table = monster_entity.components.get(LootTable)
    if not table:
        return
    pos = monster_entity.components[Position]
    active_map = monster_entity.relation_tag["InMap"]
    log = world[None].components[("MessageLog", list)]
    
    for factory, percentage_chance in table.chances:

        if random.randint(1, 100) <= percentage_chance:
            # Drop the item!
            dropped_item = factory(world, active_map, pos)
            
            # Determine item display name string
            item_name = dropped_item.components.get(Name)
            log.append(f"The monster dropped a {item_name}!")

def drop_monster_equipment(world:tcod.ecs.Registry,monster:tcod.ecs.Entity) -> None:
    """Finds monster-equipped gear, un-equips, and drops on ground."""
    pos = monster.components.get(Position)
    active_map = monster.relation_tag.get("InMap")
    log = world[None].components[("MessageLog",list)]
    if not pos or not active_map:
        return
    all_equippables = world.Q.all_of(components=[Equippable])
    monster_gear = [item for item in all_equippables if item.relation_tag.get("EquippedIn") == monster]
    for gear in monster_gear:
        del gear.relation_tag["EquippedIn"]
        gear.components[Position] = pos
        gear.tags.add(pos)
        gear.tags.add(IsItem)
        gear.relation_tag["InMap"] = active_map
        gear_name = gear.components[Name]
        gear_msg = f"The monster dropped its {gear_name}!"
        log.append(gear_msg)

def buy_item_from_merchant(world:tcod.ecs.Registry,buyer:tcod.ecs.Entity,actor:tcod.ecs.Entity,item:tcod.ecs.Entity) -> bool:
    """Processes buying an item from a merchant. Returns True if successful."""
    log = world[None].components[("MessageLog",list)]
    item_price = item.components[Price].value if Price in item.components else 25
    item_name = item.components.get(Name,"Unknown")
    buyer_gold = buyer.components.get(Gold,0)
    if buyer_gold < item_price:
        poor_msg = f"You don't have enough gold to buy the {item_name}!"
        log.append(poor_msg)
        return False
    buyer.components[Gold] -= item_price
    actor.components[Gold] += item_price
    del item.relation_tag["InInventoryOf"]
    item.relation_tag["InInventoryOf"] = buyer
    buy_msg = f"You gave the merchant {item_price}g for the {item_name}."
    log.append(buy_msg)
    return True

def sell_item_to_merchant(world:tcod.ecs.Registry,seller:tcod.ecs.Entity,merchant:tcod.ecs.Entity,item:tcod.ecs.Entity) -> None:
    """Processes selling an item back to the merchant for half value."""
    log = world[None].components[("MessageLog",list)]
    item_name = item.components[Name]
    base_val = item.components[Price].value if Price in item.components else 30
    sell_value = max(5,base_val//2)
    if item.relation_tag.get("EquippedIn") == seller:
        del item.relation_tag["EquippedIn"]
    if item.relation_tag.get("InInventoryOf") == seller:
        del item.relation_tag["InInventoryOf"]
    item.relation_tag["InInventoryOf"] = merchant
    seller.components[Gold] += sell_value
    sell_msg = f"You sold the {item_name} for {sell_value}g."
    log.append(sell_msg)

def cast_special_ability(world:tcod.ecs.Registry,actor:tcod.ecs.Entity,skill_type:AbilityType) -> bool:
  """Processes dynamic special ability logic. Returns True if successful."""
  log = world[None].components[("MessageLog",list)]
  skills = actor.components.get(("Skills",list), [])
  ability = next((s for s in skills if s.AbilityType==skill_type),None)
  if not ability:
      return False
    
