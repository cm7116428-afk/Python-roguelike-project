"""Collection of common tags"""

from __future__ import annotations
from typing import Final

IsPlayer: Final = "IsPlayer"
"""Entity is the player"""

IsMerchant: Final = "IsMerchant"
"""Entity is an NPC merchant"""

IsActor: Final = "IsActor"
"""Entity is an actor"""

IsItem: Final = "IsItem"
"""Entity is an item"""

IsMap: Final = "IsMap"
"""Entity is a randomly generated map"""

IsMonster: Final = "IsMonster"
"""Entity is a monster"""

BlocksMovement: Final = "BlocksMovement"
"""Entity prevents player from moving to this coordinate"""

IsStairs: Final = "IsStairs"
"""Entity is a staircase."""

InInventoryOf: Final = "InInventoryOf"
"""Entity is in an actor's inventory."""

IsPotion: Final = "IsPotion"
"""Entity is a consumable potion."""

IsScroll: Final = "IsScroll"
"""Entity is a consumable magic scroll."""

IsChest: Final = "IsChest"
"""Entity is a container chest."""