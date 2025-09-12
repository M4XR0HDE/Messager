import sqlite3
import os
import re

class Player:#create on player object
    def __init__(self, name):#declaring player attributes
        self.name = name
        self.inventory = []
        self.health = 100
        self.location = "Starting Room"
        self.base_attack = 5
        self.attack_power = self.base_attack
        self.equipped_weapon = None
        self.inventory.append(stick)
        self.equip_weapon("Stick")

    def add_item(self, item):#function to add items into the inventory
        self.inventory.append(item)
        if isinstance(item, Item):
            print(f"{item.name} has been added to {self.name}'s inventory.")
        else:
            print(f"{item} has been added to {self.name}'s inventory.")

    def remove_item(self, item):#function to remove items from the inventory
        if item in self.inventory:
            self.inventory.remove(item)
            if isinstance(item, Item):
                print(f"{item.name} has been removed from {self.name}'s inventory.")
            else:
                print(f"{item} has been removed from {self.name}'s inventory.")
        else:
            if isinstance(item, Item):
                print(f"{item.name} not found in inventory.")
            else:
                print(f"{item} not found in inventory.")

    def show_inventory(self):#function to display the inventory
        print(f"{self.name}'s Inventory:")
        for item in self.inventory:
            if isinstance(item, Item):
                equipped = " (equipped)" if self.equipped_weapon == item else ""
                print(f" - {item.name}{equipped}")
            else:
                print(f" - {item}")
        if self.equipped_weapon:
            print(f"Equipped weapon: {self.equipped_weapon.name} (+{self.equipped_weapon.value} attack)")

    def equip_weapon(self, item_name):#function to equip a weapon
        weapons = [item for item in self.inventory if isinstance(item, Item)]
        for item in weapons:
            if item.name == item_name:
                if not item.is_weapon:
                    print(f"{item.name} is not a weapon and cannot be equipped.")
                    return
                if self.equipped_weapon:
                    print(f"You already have {self.equipped_weapon.name} equipped. Remove it first.")
                    return
                self.equipped_weapon = item
                self.attack_power = self.base_attack + (item.value if item.value else 0)
                print(f"You equipped {item.name}. Attack is now {self.attack_power}.")
                return
        print(f"{item_name} not found in inventory.")

    def unequip_weapon(self):#function to unequip a weapon
        if self.equipped_weapon:
            print(f"You unequipped {self.equipped_weapon.name}.")
            # Put weapon back in inventory if not already there
            if self.equipped_weapon not in self.inventory:
                self.inventory.append(self.equipped_weapon)
            self.equipped_weapon = None
            self.attack_power = self.base_attack
        else:
            print("No weapon is currently equipped.")

    def attack(self, target):#function to attack
        if target.health > 0:
            damage = self.attack_power
            target.health -= damage
            print(f"{self.name} attacks {target.name} for {damage} damage.")
            if target.health <= 0:
                print(f"{target.name} has been defeated.")
        else:
            print(f"{target.name} is already defeated.")

class Ally:
    def __init__(self, name, health, base_attack, location=None, type=None):
        self.name = name
        self.health = health
        self.base_attack = base_attack
        self.location = location
        self.type = type
    def is_alive(self):
        return self.health > 0

    def show_info(self):
        print(f"Ally: {self.name}")
        print(f"Type: {self.type}")
        print(f"Health: {self.health}")
        print(f"Base Attack: {self.base_attack}")

class Enemy:#object for enemy
    def __init__(self, name, health, attack_power, has_defeat_interaction=None, defeat_interaction_effect=None):#declaring enemy attributes
        self.name = name
        self.health = health
        self.attack_power = attack_power
        self.location = "Enemy Room"
        self.looted = False  # Track if enemy has been looted
        self.has_defeat_interaction = has_defeat_interaction  # Item name that triggers interaction
        self.defeat_interaction_effect = defeat_interaction_effect  # Effect function to call

    def attack(self, target):#attack function for enemies
        if target.health > 0:
            damage = self.attack_power
            target.health -= damage
            print(f"{self.name} attacks {target.name} for {damage} damage.")
            if target.health <= 0:
                print(f"{target.name} has been defeated.")
        else:
            print(f"{target.name} is already defeated.")

class Item:#object for item
    def __init__(self, name, description, usage, effect=None, value=None, is_weapon=False):#declaring item attributes
        self.name = name
        self.description = description
        self.usage = usage
        self.effect = effect
        self.value = value
        self.is_weapon = is_weapon

    def show_info(self):#function to display item information
        print(f"Item: {self.name}")
        print(f"Description: {self.description}")
        print(f"Usage: {self.usage}")

#Functions
def turn_ally(enemy, location):
    ally_name = input(f"What do you want to name your {enemy.name}: ")
    type_name = re.sub(r'\d+', '', enemy.name)
    new_ally = Ally(name=ally_name, health=enemy.health, base_attack=enemy.attack_power, location=location, type=type_name)
    allies.append(new_ally)
    # Remove enemy from enemies list
    if enemy in enemies:
        enemies.remove(enemy)
    print(f"{ally_name} is now your ally!")

def heal_player(player, amount):#a basic healing function can be used for potions or other things
    player.health += amount
    if isinstance(player, Enemy):
        print(f"{player.name}'s Health increased by {amount}. Current Health: {player.health}")
    elif isinstance(player, Ally):
        print(f"{player.name} feels rejuvenated! Health increased by {amount}. Current health: {player.health}")
    else:
        print(f"You feel rejuvenated! Health increased by {amount}. Current health: {player.health}")

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')
    print("\033c", end="")  # ANSI escape code for extra clearing

#creating starter items
stick = Item(
    name="Stick",
    description="It's useless but it's something.",
    usage="Use to deal 5 damage.",
    value=5,
    is_weapon=True
)

#creating weapons
sword = Item(
    name="Sword",
    description="A sharp steel sword. Useful for fighting enemies.",
    usage="Use to increase attack damage by 20.",
    value=20,
    is_weapon=True
)

#creating healing items
big_healing_flask = Item(
    name="Big Healing Flask",
    description="A large flask filled with a glowing red liquid. Restores health when used.",
    usage="Use to restore 50 health points.",
    effect=lambda player: heal_player(player, 50),
    value=50,
    is_weapon=False
)

#creating Random Items
Bone = Item(name="Bone", description="A bone from a defeated skeleton.", usage="Maybe it's useful.", value=5)

class Map:#object for map
    def __init__(self):#create rooms and connection to other rooms
        self.rooms = {
            "Starting Room": {
                "description": "You are in a dimly lit room.",
                "exits": {"north": "Treasure Room", "south": "Armory"}
            },
            "Treasure Room": {
                "description": "You see a pile of gold coins.",
                "exits": {"south": "Starting Room"}
            },
            "Armory": {
                "description": "You are in the armory. There are weapons on the wall and two Skeletons guarding the room.",
                "exits": {"north": "Starting Room"},
                "items": [sword]
            }
        }
        #declare items or enemies if not already configures in room
        self.rooms["Starting Room"]["Enemies"] = ["Goblin"]
        self.rooms["Armory"]["Enemies"] = ["Skeleton1", "Skeleton2"]
        self.rooms["Treasure Room"]["items"] = [big_healing_flask]

    def get_room(self, room_name):
        return self.rooms.get(room_name)

# Initializing game elements
game_map = Map()

#creating enemies
Goblin_starter = Enemy("Goblin", health=50, attack_power=5)
Ogre_starter_boss = Enemy("Ogre", health=100, attack_power=20)
Skeleton1_starter = Enemy("Skeleton1", health=30, attack_power=10, has_defeat_interaction="Bone", defeat_interaction_effect=lambda enemy: (heal_player(enemy, 5), turn_ally(enemy, enemy.location)))
Skeleton2_starter = Enemy("Skeleton2", health=10, attack_power=20, has_defeat_interaction="Bone", defeat_interaction_effect=lambda enemy: (heal_player(enemy, 5), turn_ally(enemy, enemy.location)))

#placing enemies into rooms
Goblin_starter.location = "Starting Room"
Skeleton1_starter.location = "Armory"
Skeleton2_starter.location = "Armory"
Ogre_starter_boss.location = "Treasure Room"

enemies = [
    Goblin_starter,
    Ogre_starter_boss,
    Skeleton2_starter,
    Skeleton1_starter
]#enemy list for coding logic

# Add a list to hold allies
allies = []
# Example: create an ally
# allies.append(Ally("Companion", 50, 7))


#character naming loop
while 1:
    player_name = input("Enter your player's name: ")
    if player_name.strip():
        break
    print("Player name cannot be empty. Please try again.")
#if player_name not in (placeholder to look through savegame)
#if exist load savegame
#else
player = Player(player_name)
clear_screen()
#main loop

while 1:
    if player.health <= 0:
        print(f"{player.name} has been defeated.")
        input("Game Over")
        break
    room = game_map.get_room(player.location)
    available_actions = ["move", "attack", "inventory", "look", "quit"]
    show_collect = False
    action = input(f"What would you like to do? ({', '.join(available_actions)}) ")
    clear_screen()

    print(f"you are in {player.location}")
    # Show all enemies and allies in the current room (alive or defeated)
    # Remove enemies that have turned into allies
    ally_types_in_room = [ally.type for ally in allies if ally.location == player.location]
    room_enemies = [enemy for enemy in enemies if enemy.location == player.location and enemy.name not in ally_types_in_room]
    room_allies = [ally for ally in allies if ally.location == player.location]
    if room_enemies or room_allies:
        print("Enemies here:")
        for enemy in room_enemies:
            if enemy.health > 0:
                print(f" - {enemy.name} (HP: {enemy.health})")
            else:
                print(f" - {enemy.name} (defeated)")
        if room_allies:
            print("Allies here:")
            for ally in room_allies:
                print(f" - {ally.name} (HP: {ally.health}, Type: {ally.type})")

    # Loot defeated enemies
    defeated_enemies = [enemy for enemy in room_enemies if enemy.health <= 0 and not getattr(enemy, 'looted', False)]
    if defeated_enemies:
        loot_action = input("Would you like to loot a defeated enemy? (yes/no): ")
        if loot_action == "yes":
            print("Defeated enemies:")
            for enemy in defeated_enemies:
                print(f" - {enemy.name}")
            loot_name = input("Which enemy would you like to loot? ")
            loot_target = next((enemy for enemy in defeated_enemies if enemy.name == loot_name), None)
            if loot_target:
                loot_item = Item(name="Bone", description="A bone from a defeated skeleton.", usage="Maybe it's useful.")
                player.add_item(loot_item)
                loot_target.looted = True
                print(f"You looted {loot_item.name} from {loot_target.name}.")
            else:
                print("No such defeated enemy to loot.")

    if action == "move":
        room = game_map.get_room(player.location)
        if room:
            print(f"Available exits: {', '.join(room['exits'].keys())}")
            direction = input("Which direction? ")
            if direction in room["exits"]:
                new_room = room["exits"][direction]
                player.location = new_room
                # Move all allies with the player
                for ally in allies:
                    if ally.health <= 0:
                        continue
                    else:
                        ally.location = new_room
                print(f"You move {direction} to the {new_room}.")
            else:
                print("You can't go that way.")
        else:
            print("You are in an unknown location and cannot move.")

    elif action == "attack":
        target_name = input("Who would you like to attack? ")
        target = next((enemy for enemy in room_enemies if enemy.name == target_name and enemy.health > 0), None)
        if target:
            player.attack(target)
            if target.health > 0:
                # If player would take damage, redirect to ally if present
                if allies:
                    # Find ally in same room
                    room_allies = [ally for ally in allies if hasattr(ally, 'location') and ally.location == player.location]
                    if room_allies:
                        ally = room_allies[0]
                        if ally.is_alive():
                            damage = target.attack_power
                            ally.health -= damage
                            print(f"{ally.name} takes {damage} damage instead of you! Ally health: {ally.health}")
                            if ally.health <= 0:
                                print(f"{ally.name} has been defeated!")
                        else:
                            print("No Allies to tank the Damage.")
                            target.attack(player)
                    else:
                        target.attack(player)
                else:
                    target.attack(player)
            else:
                # Enemy was just defeated, loot immediately if not already looted
                if not getattr(target, 'looted', False):
                    player.add_item(Bone)
                    target.looted = True
                    print(f"You looted {Bone.name} from {target.name}.")
        else:
            print("Target not found or already defeated.")

    elif action == "inventory":
        clear_screen()
        while True:
            print(f"Current Player Health: {player.health}")
            player.show_inventory()
            inv_action = input("Inventory options: use, throw, info, equip, unequip, allyinfo, back > ")
            clear_screen()
            if inv_action == "allyinfo":
                if allies:
                    print("Allies:")
                    for ally in allies:
                        print(f" - {ally.name}")
                    ally_name = input("Enter the name of the ally to view info: ")
                    found_ally = next((ally for ally in allies if ally.name == ally_name), None)
                    if found_ally:
                        found_ally.show_info()
                        print(f"Location: {found_ally.location}")
                    else:
                        print("Ally not found.")
                else:
                    print("You have no allies.")
                continue
            if inv_action == "use":
                # Show all usable (non-weapon) items
                usable_items = [item for item in player.inventory if isinstance(item, Item) and not item.is_weapon]
                if usable_items:
                    print("Usable items:")
                    for item in usable_items:
                        print(f" - {item.name}")
                else:
                    print("No usable items in inventory.")
                item_name = input("Enter the name of the item to use: ")
                found_item = None
                for item in usable_items:
                    if item.name == item_name:
                        found_item = item
                        break
                if found_item:
                    # Show list of allies before target prompt
                    if allies:
                        print("Allies:")
                        for ally in allies:
                            print(f" - {ally.name}")
                    use_target = input("Use on: 'player' or enter ally name > ").strip()
                    if use_target.lower() == "player":
                        target = player
                    else:
                        target = next((ally for ally in allies if ally.name == use_target), None)
                        if not target:
                            print("Ally not found. Try again.")
                            continue
                    if isinstance(found_item, Item) and found_item.effect:
                        try:
                            found_item.effect(target)
                            player.remove_item(found_item)
                        except Exception:
                            print("Item effect could not be applied.")
                    else:
                        print("Item cannot be used.")
                else:
                    print("Item not found in inventory.")

            elif inv_action == "throw":
                if player.inventory:
                    print("Your inventory:")
                    for item in player.inventory:
                        if isinstance(item, Item):
                            print(f" - {item.name}")
                        else:
                            print(f" - {item}")
                    item_name = input("Which item would you like to throw away? ")
                    found_item = None
                    for item in player.inventory:
                        if (isinstance(item, Item) and item.name == item_name) or (item == item_name):
                            found_item = item
                            break
                    if found_item:
                        # Prevent throwing equipped weapon
                        if isinstance(found_item, Item) and player.equipped_weapon == found_item:
                            print("You can't throw away an equipped item. Please unequip it first.")
                        else:
                            print("Do you want to place it in the room or throw it at an enemy?")
                            throw_choice = input("Type 'room' to place in room, 'enemy' to throw at enemy: ")
                            if throw_choice == "room":
                                player.remove_item(found_item)
                                room = game_map.get_room(player.location)
                                if room is not None:
                                    if "items" not in room:
                                        room["items"] = []
                                    room["items"].append(found_item)
                                    print(f"{item_name} has been placed in the room.")
                            elif throw_choice == "enemy":
                                if room_enemies:
                                    print("Enemies here:")
                                    for enemy in room_enemies:
                                        status = "defeated" if enemy.health <= 0 else f"HP: {enemy.health}"
                                        print(f" - {enemy.name} ({status})")
                                    target_name = input("Which enemy do you want to throw the item at? ")
                                    target = next((enemy for enemy in room_enemies if enemy.name == target_name), None)
                                    clear_screen()
                                    if target:
                                        if target.health <= 0:
                                            confirm = input(f"{target.name} is already defeated. Are you sure you want to throw the item at it? (yes/no): ").strip().lower()
                                            if confirm != "yes":
                                                print("Throw cancelled.")
                                                continue
                                            # Defeat interaction: if enemy has one, call effect if item matches
                                            if hasattr(target, 'has_defeat_interaction') and hasattr(target, 'defeat_interaction_effect'):
                                                if isinstance(found_item, Item) and found_item.name == target.has_defeat_interaction:
                                                    print(f"You throw {item_name} at {target.name}. You lost the item!")
                                                    print(f"Secret interaction triggered for {target.name}!")
                                                    target.defeat_interaction_effect(target)
                                                    player.remove_item(found_item)
                                                    continue  # Skip the rest of the throwing logic
                                        print(f"You throw {item_name} at {target.name}. You lost the item!")
                                        player.remove_item(found_item)
                                        # Apply item effect or weapon damage to enemy
                                        if isinstance(found_item, Item):
                                            if found_item.effect:
                                                try:
                                                    found_item.effect(target)
                                                except Exception:
                                                    print("Item effect could not be applied to enemy.")
                                            elif found_item.value:
                                                target.health -= found_item.value
                                                print(f"{target.name} takes {found_item.value} damage from the thrown weapon!")
                                                if target.health <= 0:
                                                    print(f"{target.name} has been defeated.")
                                    else:
                                        print("Enemy not found.")
                                else:
                                    print("No enemies to throw the item at.")
                            else:
                                print("Invalid choice. Item not thrown.")
                    else:
                        print("Item not found in inventory.")
                else:
                    print("Your inventory is empty.")

            elif inv_action == "info":
                item_name = input("Enter the name of the item to view info: ")
                found_item = None
                clear_screen()
                for item in player.inventory:
                    if isinstance(item, Item) and item.name == item_name:
                        found_item = item
                        break
                if found_item:
                    found_item.show_info()
                else:
                    print("Item not found or has no info.")

            elif inv_action == "equip":
                # Print all weapons in inventory before asking for input
                weapons = [item for item in player.inventory if isinstance(item, Item) and item.is_weapon]
                print("Weapons in your inventory:")
                for weapon in weapons:
                    print(f" - {weapon.name} (Attack: {weapon.value})")
                item_name = input("Enter the name of the weapon to equip: ")
                player.equip_weapon(item_name)

            elif inv_action == "unequip":
                player.unequip_weapon()

                print("Weapon unequipped.")
            elif inv_action == "back":
                break

            else:
                print("Invalid inventory option.")

    elif action == "look":
        room = game_map.get_room(player.location)
        if room:
            print(room["description"])
            if "items" in room and room["items"]:
                print("Items in this room:")
                for item in room["items"]:
                    if isinstance(item, Item):
                        print(f" - {item.name}")
                    else:
                        print(f" - {item}")
                show_collect = True
        else:
            print("You see nothing special.")
        # After look, if items are present, offer collect
        if show_collect:
            collect_action = input("Would you like to collect an item? (yes/no): ")
            if collect_action == "yes":
                print("Items available to collect:")
                for item in room["items"]:
                    print(f" - {item.name}" if isinstance(item, Item) else f" - {item}")
                item_name = input("Which item would you like to collect? ")
                found_item = None
                for item in room["items"]:
                    if (isinstance(item, Item) and item.name == item_name) or (item == item_name):
                        found_item = item
                        break
                if found_item:
                    player.add_item(found_item)
                    room["items"].remove(found_item)
                else:
                    print("Item not found.")

    elif action == "collect":
        room = game_map.get_room(player.location)
        if room and "items" in room and room["items"]:
            print("Items available to collect:")
            for item in room["items"]:
                if isinstance(item, Item):
                    print(f" - {item.name}")
            item_name = input("Which item would you like to collect? ")
            found_item = None
            for item in room["items"]:
                if (isinstance(item, Item) and item.name == item_name) or (item == item_name):
                    found_item = item
                    break
            if found_item:
                player.add_item(found_item)
                room["items"].remove(found_item)
            else:
                print("Item not found.")
        else:
            print("There are no items to collect here.")
        if room and "items" in room and room["items"]:
            print("Items available to collect:")
            for item in room["items"]:
                if isinstance(item, Item):
                    item.show_info()
                else:
                    print(f" - {item}")
                item_name = input("Which item would you like to collect? ")
                found_item = None
                for item in room["items"]:
                    if (isinstance(item, Item) and item.name == item_name) or (item == item_name):
                        found_item = item
                        break
                if found_item:
                    player.add_item(found_item)
                    room["items"].remove(found_item)
                else:
                    print("Item not found.")

    elif action == "quit":
        print("See ya next time!")
        break
    else:
        print("Invalid action.")