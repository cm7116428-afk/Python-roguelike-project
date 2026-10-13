"""Functions for creating entities in the game world."""

from __future__ import annotations
import random
import tcod
import tcod.ecs
from game.components import AbilityData, AbilityType, Price, Chest, DownStairs, UpStairs, Equippable, EquipmentSlot, Experience, ExperienceBounty, Fighter, Gold, Graphic, Heal, HotkeyMap, Item, LootTable, Name, Position, LightningDamage, ChainLightningDamage, FireballDamage
from game.tags import BlocksMovement, IsActor, IsItem, IsPlayer, IsPotion, IsMonster, IsScroll, IsStairs, IsChest, IsMerchant

###Player###
def spawn_player(world:tcod.ecs.Registry,pos:Position) -> tcod.ecs.Entity:
    player=world.new_entity()
    player.tags.add(IsActor)
    player.tags.add(IsPlayer)
    player.tags.add(BlocksMovement)
    player.tags.add(pos)

    player.components[Position] = pos
    player.components[Graphic] = Graphic(ch=ord("@"), fg=(255,255,255))
    player.components[Name] = "Player"
    player.components[Fighter] = Fighter(hp=30,max_hp=30,defense=2,power=5)
    player.components[Experience] = Experience(current_xp=0,level=1,xp_to_next_level=200)
    starting_weapon = spawn_dagger(world,pos=None)
    starting_weapon.relation_tag["EquippedIn"] = player
    starting_armor = spawn_leather_armor(world,pos=None)
    starting_armor.relation_tag["EquippedIn"] = player
    player.components[HotkeyMap] = HotkeyMap()
    player.components[("Skills",list)] = [
        AbilityData(name="Holy Burst",ability_type=AbilityType.HEAL_BURST,cost=15,param=12),
        AbilityData(name="Cleave Slice",ability_type=AbilityType.CLEAVE_ATTACK,cost=20,param=6)
    ]
    return player

def spawn_merchant(world:tcod.ecs.Registry,map_entity:tcod.ecs.Entity,pos:Position) -> tcod.ecs.Entity:
    merchant = world.new_entity()
    merchant.tags.add(pos)
    merchant.tags.add(IsMerchant)
    merchant.tags.add(BlocksMovement)

    merchant.components[Position] = pos
    merchant.components[Graphic] = Graphic(ch=ord("M"),fg=(255,105,180)) #Pink M
    merchant.components[Name] = "Merchant"
    merchant.relation_tag["InMap"] = map_entity
    stock_factory = [
        (spawn_healing_potion, 50),
        (spawn_healing_potion, 50),
        (spawn_lightning_scroll, 75),
        (spawn_sword, 150),
        (spawn_chain_mail, 200), 
    ]
    for factory, cost in stock_factory:
        items = factory(world=world,map_entity=map_entity,pos=None)
        items.components[Price] = Price(value=cost)
        items.relation_tag["InInventoryOf"] = merchant
    return merchant


###Stairs###
def spawn_downstairs(world:tcod.ecs.Registry,map_entity:tcod.ecs.Entity,pos:Position) -> tcod.ecs.Entity:
    dstairs = world.new_entity()
    dstairs.tags.add(pos)
    dstairs.tags.add(IsStairs)

    dstairs.components[Position] = pos
    dstairs.components[Graphic] = Graphic(ch=ord(">"),fg=(255,255,255))
    dstairs.components[DownStairs] = DownStairs()
    dstairs.relation_tag["InMap"] = map_entity
    return dstairs

def spawn_upstairs(world:tcod.ecs.Registry,map_entity:tcod.ecs.Entity,pos:Position) -> tcod.ecs.Entity:
    ustairs = world.new_entity()
    ustairs.tags.add(pos)
    ustairs.tags.add(IsStairs)

    ustairs.components[Position] = pos
    ustairs.components[Graphic] = Graphic(ch=ord("<"),fg=(255,255,255))
    ustairs.components[UpStairs] = UpStairs()
    ustairs.relation_tag["InMap"] = map_entity
    return ustairs

###Equipment###
def spawn_dagger(world:tcod.ecs.Registry,pos:Position | None = None) -> tcod.ecs.Entity:
    item = world.new_entity()
    item.tags.add(IsItem)
    
    item.components[Graphic] = Graphic(ch=ord("-"),fg=(0,191,255)) #Light blue
    item.components[Item] = Item()
    item.components[Name] = "Dagger"
    item.components[Equippable] = Equippable(slot=EquipmentSlot.MAIN_HAND,power_bonus=2)
    if pos:
        item.components[Position] = pos
        item.tags.add(pos)
    return item

def spawn_leather_armor(world:tcod.ecs.Registry,pos:Position | None = None) -> tcod.ecs.Entity:
    item = world.new_entity()
    item.tags.add(IsItem)

    item.components[Graphic] = Graphic(ch=ord("&"),fg=(139,69,19)) #Brown armor
    item.components[Item] = Item()
    item.components[Name] = "Leather Armor"
    item.components[Equippable] = Equippable(slot=EquipmentSlot.BODY, defense_bonus=1)
    if pos:
        item.components[Position] = pos
        item.tags.add(pos)
    return item

def spawn_sword(world:tcod.ecs.Registry,map_entity:tcod.ecs.Entity,pos:Position) -> tcod.ecs.Entity:
    item = world.new_entity()
    item.tags.add(IsItem)
    item.components[Graphic] = Graphic(ch=ord("/"),fg=(192,192,192)) #Silver
    item.components[Item] = Item()
    item.components[Name] = "Sword"
    item.components[Equippable] = Equippable(slot=EquipmentSlot.MAIN_HAND,power_bonus=4)
    item.components[Position] = pos
    item.tags.add(pos)
    item.relation_tag["InMap"] = map_entity
    return item

def spawn_chain_mail(world:tcod.ecs.Registry,map_entity:tcod.ecs.Entity,pos:Position) -> tcod.ecs.Entity:
    item = world.new_entity()
    item.tags.add(IsItem)
    item.components[Graphic] = Graphic(ch=ord("&"),fg=(169,169,169)) #Grey
    item.components[Item] = Item()
    item.components[Name] = "Chain Mail"
    item.components[Equippable] = Equippable(slot=EquipmentSlot.BODY,defense_bonus=3)
    item.components[Position] = pos
    item.tags.add(pos)
    item.relation_tag["InMap"] = map_entity
    return item

###Items###
def spawn_gold(world:tcod.ecs.Registry,map_entity:tcod.ecs.Entity,pos:Position) -> tcod.ecs.Entity:
    gold_item = world.new_entity()
    gold_item.tags.add(IsItem)
    gold_item.tags.add(pos) #Tag coordinates for lookups
    
    gold_item.components[Position] = pos
    gold_item.components[Graphic] = Graphic(ch=ord("$"),fg=(255,223,0))
    gold_item.components[Gold] = random.randint(1,50)
    gold_item.relation_tag["InMap"] = map_entity
    return gold_item

def spawn_healing_potion(world: tcod.ecs.Registry,map_entity:tcod.ecs.Entity,pos:Position) -> tcod.ecs.Entity:
    hpotion = world.new_entity()
    hpotion.tags.add(IsItem)
    hpotion.tags.add(IsPotion)
    hpotion.tags.add(pos)

    hpotion.components[Position] = pos
    hpotion.components[Graphic] = Graphic(ch=ord("!"),fg=(127,0,255)) #Burple
    hpotion.components[Item] = Item()
    hpotion.components[Name] = "Healing Potion"
    hpotion.components[Heal] = Heal(amount=random.randint(2,8))
    hpotion.relation_tag["InMap"] = map_entity
    return hpotion

def spawn_lightning_scroll(world:tcod.ecs.Registry,map_entity:tcod.ecs.Entity,pos:Position) -> tcod.ecs.Entity:
    lscroll = world.new_entity()
    lscroll.tags.add(IsItem)
    lscroll.tags.add(IsScroll)
    lscroll.tags.add(pos)

    lscroll.components[Position] = pos
    lscroll.components[Graphic] = Graphic(ch=ord("?"),fg=(255,255,0)) #Yellow
    lscroll.components[Item] = Item()
    lscroll.components[Name] = "Lightning Scroll"
    lscroll.components[LightningDamage] = LightningDamage(damage=12,max_range=3)
    lscroll.relation_tag["InMap"] = map_entity
    return lscroll

def spawn_chain_lightning_scroll(world:tcod.ecs.Registry,map_entity:tcod.ecs.Entity,pos:Position) -> tcod.ecs.Entity:
    clscroll = world.new_entity()
    clscroll.tags.add(IsItem)
    clscroll.tags.add(IsScroll)
    clscroll.tags.add(pos)

    clscroll.components[Position] = pos
    clscroll.components[Graphic] = Graphic(ch=ord("?"),fg=(0,255,255)) #Bright Cyan
    clscroll.components[Item] = Item()
    clscroll.components[Name] = "Chain Lightning Scroll"
    clscroll.components[ChainLightningDamage] = ChainLightningDamage(damage=20,range=5,jumps=4)
    clscroll.relation_tag["InMap"] = map_entity
    return clscroll

def spawn_fireball_scroll(world:tcod.ecs.Registry,map_entity:tcod.ecs.Entity,pos:Position) -> tcod.ecs.Entity:
    fscroll = world.new_entity()
    fscroll.tags.add(IsItem)
    fscroll.tags.add(IsScroll)
    fscroll.tags.add(pos)

    fscroll.components[Position] = pos
    fscroll.components[Graphic] = Graphic(ch=ord("?"),fg=(255,0,0)) #Red
    fscroll.components[Item] = Item()
    fscroll.components[Name] = "Fireball Scroll"
    fscroll.components[FireballDamage] = FireballDamage(damage=15,radius=5)
    fscroll.relation_tag["InMap"] = map_entity
    return fscroll

def spawn_chest(world:tcod.ecs.Registry,map_entity:tcod.ecs.Entity,pos:Position) -> tcod.ecs.Entity:
    chest = world.new_entity()
    chest.tags.add(IsChest)
    chest.tags.add(BlocksMovement)
    chest.tags.add(pos)

    chest.components[Position] = pos
    chest.components[Graphic] = Graphic(ch=ord("="),fg=(218,165,32))
    chest.components[Chest] = Chest(is_open=False)
    chest.relation_tag["InMap"] = map_entity
    return chest

###Enemies###
def spawn_orc(world:tcod.ecs.Registry,map_entity:tcod.ecs.Entity,pos:Position) -> tcod.ecs.Entity:
    orc = world.new_entity()
    orc.tags.add(IsActor)
    orc.tags.add(IsMonster)
    orc.tags.add(BlocksMovement)
    orc.tags.add(pos)

    orc.components[Position] = pos
    orc.components[Graphic] = Graphic(ch=ord("o"),fg=(63,127,63))
    orc.components[Name] = "Orc"
    orc.relation_tag["InMap"] = map_entity
    orc.components[Fighter] = Fighter(hp=10,max_hp=10,defense=0,power=3,)
    orc.components[ExperienceBounty] = ExperienceBounty(amount=35)
    orc.components[LootTable] = LootTable(chances=[
        (spawn_gold, 40),
        (spawn_healing_potion, 15)
    ])
    if random.random() < 0.6:
        orc_weapon = spawn_dagger(world,pos=None)
        orc_weapon.relation_tag["EquippedIn"] = orc
    if random.random() <0.3:
        orc_armor = spawn_leather_armor(world,pos=None)
        orc_armor.relation_tag["EquippedIn"] = orc
    return orc

def spawn_troll(world:tcod.ecs.Registry,map_entity:tcod.ecs.Entity,pos:Position) -> tcod.ecs.Entity:
    troll = world.new_entity()
    troll.tags.add(IsActor)
    troll.tags.add(IsMonster)
    troll.tags.add(BlocksMovement)
    troll.tags.add(pos)

    troll.components[Position] = pos
    troll.components[Graphic] = Graphic(ch=ord("T"),fg=(0,127,0))
    troll.components[Name] = "Troll"

    troll.relation_tag["InMap"] = map_entity
    troll.components[Fighter] = Fighter(hp=16,max_hp=16,defense=1,power=4,)
    troll.components[ExperienceBounty] = ExperienceBounty(amount=100)
    troll.components[LootTable] = LootTable(chances=[
        (spawn_gold, 30)])
    troll_weapon = spawn_sword(world,map_entity,pos=None)
    troll_weapon.relation_tag["EquippedIn"] = troll
    if random.random() < 0.3:
        troll_armor = spawn_chain_mail(world,map_entity,pos=None)
        troll_armor.relation_tag["EquippedIn"] = troll
    return troll