# Python-roguelike-project
A simple roguelike written in Python, using the python-tcod library.  Currently in work.

Controls:
Use the keypad to move around, or W-A-X-D with Q-E-Z-C as diagonals, or the arrow keys with Home, End, Page Up, and Page Down as diagonals.
Walking over gold $ will automatically pick it up and add it to your total. It serves no other purpose (yet!).
Bump into enemies (o, T) to do a melee attack. Your attacks and the enemy's will show up in the message log at the bottom of the game screen.
G: pick up item (!, ?) at player location
! are health potions, ? are scrolls. The yellow scrolls are Lightning, the red are Fireball.
I: open inventory
  in inventory: D to drop item, U to use item
  Using a Fireball scroll will bring up a targeting reticule *. Navigate to where you would like to cast the fireball, and press Return or Enter on the keypad. Be careful!
When the player is standing on a down staircase >, press the period button or enter on the keypad to go down the stairs.
There are no up staircases (yet!).
