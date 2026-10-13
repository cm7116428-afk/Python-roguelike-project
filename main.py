"""Main entry-point module. The script used to start the game."""

from __future__ import annotations
import g
import tcod.context
import tcod.ecs
import tcod.tileset
import game.state_tools
import game.states

def main() -> None:
    #Entry point function
    g.world = tcod.ecs.Registry()
    
    g.world[None].components[("MessageLog",list)] = ["Welcome to the Dungeon!"]

    #tileset = tcod.tileset.load_tilesheet(
    #    r"C:\Users\N18998\projects\.venv\data\Alloy_curses_12x12.png", columns=16, rows=16, charmap=tcod.tileset.CHARMAP_CP437
    #)
    #tileset += tcod.tileset.procedural_block_elements(shape=tileset.tile_shape)
    g.console=tcod.console.Console(80,51)
    
    g.states=[game.states.MainMenu(world=g.world)]
    
    with tcod.context.new(console=g.console,
                          #tileset=tileset
                          ) as g.context:
        game.state_tools.main_loop()
        

if __name__ == "__main__":
    main()