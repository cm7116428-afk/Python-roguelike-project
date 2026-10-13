"""Collection of common components"""

from __future__ import annotations
from typing import Final, Self
from dataclasses import dataclass, field
from enum import Enum, auto
import attrs
import numpy as np
import tcod.ecs
import tcod.ecs.callbacks
from tcod.ecs import Entity

@attrs.define(frozen=True)
class Position:
    """An entity's position"""

    x: int
    y: int

    def __add__(self, direction:tuple[int,int]) -> Self:
        """Add a vector to this position"""
        x, y = direction
        return self.__class__(self.x+x,self.y+y)
    
@tcod.ecs.callbacks.register_component_changed(component=Position)
def on_position_changed(entity: Entity, old: Position | None, new: Position | None) -> None:
    """Mirror position components as a tag"""
    if old == new: #New position is equivalent to its previous value
        return #Ignore and return
    if old is not None: #Position component removed or changed
        entity.tags.discard(old) #Remove old position from tags
    if new is not None: #Position component added or changed
        entity.tags.add(new) #Add new position to tags

@attrs.define(frozen=True)
class Graphic:
    """An entity's icon and color"""
    ch: int = ord("!")
    fg: tuple[int,int,int] = (255,255,255)

@attrs.define()
class Name(str):
    pass

Gold: Final = ("Gold",int) #Amount of gold

#Map components
#Define structured datatypes for tiles
tile_dt = np.dtype([("ch",np.int32),("fg","3u1"),("bg","3u1")])

#Define map layout components
#MapTiles: The underlying actual terrain (walls and floors)
MapTiles: Final=("MapTiles",np.ndarray)
#MapVisible: Track cells currently in FOV
MapVisible: Final=("MapVisible",np.ndarray)
#MapExplored: Track cells player has seen
MapExplored: Final=("MapExplored",np.ndarray)

@dataclass
class Fighter:
    hp: int
    max_hp: int
    defense: int
    power: int

class EquipmentSlot(Enum):
    MAIN_HAND = auto()
    BODY = auto()

@dataclass
class Equippable:
    """Component indicating an item can be equipped, providing combat modifiers."""
    slot: EquipmentSlot
    power_bonus: int = 0
    defense_bonus: int = 0

class AbilityType(Enum):
    HEAL_BURST = auto()
    CLEAVE_ATTACK = auto()

@dataclass
class AbilityData:
    """Data for player class actions and techniques"""
    name: str
    ability_type: AbilityType
    cost: int
    param: int

@dataclass
class HotkeyMap:
    """Maps number keys 1-9 to specific AbilityType triggers."""
    mappings: dict[int,AbilityType] = field(default_factory=dict)

@dataclass
class DungeonFloor:
    """Stores numerical depth level of a map entity floor layer."""
    level: int

@dataclass
class DownStairs:
    """A data component marking an entity as a staircase leading down."""
    pass

@dataclass
class UpStairs:
    """A data component marking an entity as a staircase leading up."""
    pass

@dataclass
class LootTable:
    """Stores the items and probability weights a monster can drop on death."""
    chances: list[tuple[any,int]]

@dataclass
class Item:
    """Component tag indicating that an entity can be picked up into an inventory."""
    pass

@dataclass
class Price:
    """Component storing the purchase cost of an item."""
    value: int

@dataclass
class Chest:
    """Component tag indicating an entity is a container chest."""
    is_open: bool = False

@dataclass
class Heal:
    """Component data representing restoration value of a healing item."""
    amount: int

@dataclass
class LightningDamage:
    """Deals automatic damage to the closest visible target within a max range."""
    damage: int
    max_range: int

@dataclass
class ChainLightningDamage:
    """Deals damage that chains from target to target within a set range and jump limit."""
    damage: int
    max_range: int
    max_jumps: int

@dataclass
class FireballDamage:
    """Deals damage in an explosive AOE radius at chosen coordinate."""
    damage: int
    radius: int

@dataclass
class Experience:
    """Tracks player's progression and level thresholds."""
    current_xp: int
    level: int
    xp_to_next_level: int

@dataclass
class ExperienceBounty:
    """Raw XP reward value given to the player when this entity dies."""
    amount: int

