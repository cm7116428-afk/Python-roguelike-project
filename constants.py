"""Global constants are stored here"""
from __future__ import annotations
from typing import Final
from tcod.event import KeySym

DIRECTION_KEYS: Final = {
    #Arrow keys
    KeySym.LEFT: (-1,0),
    KeySym.RIGHT: (1,0),
    KeySym.UP: (0,-1),
    KeySym.DOWN: (0,1),
    #Arrow key diagonals
    KeySym.HOME: (-1,-1),
    KeySym.END: (-1,1),
    KeySym.PAGEUP: (1,-1),
    KeySym.PAGEDOWN: (1,1),
    #Keypad
    KeySym.KP_4: (-1,0),
    KeySym.KP_6: (1,0),
    KeySym.KP_8: (0,-1),
    KeySym.KP_2: (0,1),
    KeySym.KP_7: (-1,-1),
    KeySym.KP_1: (-1,1),
    KeySym.KP_9: (1,-1),
    KeySym.KP_3: (1,1),
    #VI keys
    KeySym.A: (-1,0),
    KeySym.D: (1,0),
    KeySym.W: (0,-1),
    KeySym.X: (0,1),
    KeySym.Q: (-1,-1),
    KeySym.Z: (-1,1),
    KeySym.E: (1,-1),
    KeySym.C: (1,1),
}