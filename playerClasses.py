import pygame
import os
import assets
import math
import random
from playerProjectile import PlayerProjectile
from floating_text import FloatingText
from abilities import create_class_abilities

ASSET_DIR = os.path.join(os.path.dirname(__file__), "assets")

CLASS_REGISTRY = {
    "Ranger": {"hp": 50, "damage": 15, "armor": 5, "speed": 5, "range": 200, "attack_speed": 1.0, "attack_type": "ranged", "mana": 50, "sprite": "Ranger.png"},
    "Druid": {"hp": 70, "damage": 10, "armor": 8, "speed": 4, "range": 100, "attack_speed": 1.2, "attack_type": "ranged", "mana": 75, "sprite": "Druid.png"},
    "Witch": {"hp": 40, "damage": 20, "armor": 3, "speed": 4, "range": 150, "attack_speed": 0.8, "attack_type": "ranged", "mana": 100, "sprite": "Witch.png"},
    "Warrior": {"hp": 100, "damage": 25, "armor": 12, "speed": 3, "range": 40, "attack_speed": 1.5, "attack_type": "melee", "mana": 40, "sprite": "Warrior.png"},
}

CLASS_ABILITIES = {
    "Ranger": [
        {"name": "Multi Shot", "icon": "Multi Shot.png", "damage": 15, "desc": "Fires multiple arrows in a spread."},
        {"name": "Poison Arrow", "icon": "Poison Arrow.png", "damage": 10, "desc": "Applies poison damage over time."},
        {"name": "Volley", "icon": "Volley.png", "damage": 25, "desc": "Shoots multiple arrows rapidly."},
        {"name": "Evasion", "icon": "Evasion.png", "desc": "Quickly dodge incoming attacks."}
    ],
    "Druid": [
        {"name": "Entangle", "icon": "Entangle.png", "damage": 0, "desc": "Roots enemies in place"},
        {"name": "Healing Touch", "icon": "Healing Touch.png", "heal": 20, "desc": "Restores health"},
        {"name": "Natures Wrath", "icon": "Natures Wrath.png", "desc": "A beam of light obliterates foes."},
        {"name": "Thorns", "icon": "Thorns.png", "desc": "Enemies take damage when hitting you"}
    ],
    "Warrior": [
        {"name": "Slash", "icon": "Slash.png", "damage": 20, "desc": "Attack in a cone ahead of you"},
        {"name": "Shield Block", "icon": "Shield Block.png", "desc": "Blocks incoming damage for 5 seconds"},
        {"name": "Battle Cry", "icon": "Battle Cry.png", "desc": "Increase attack speed for 10 seconds"},
        {"name": "Whirlwind", "icon": "Whirlwind.png", "damage": 30, "desc": "Spin and hit all nearby enemies"}
    ],
    "Witch": [
        {"name": "Fireball", "icon": "Fireball.png", "damage": 25, "desc": "Shoots a blazing fireball"},
        {"name": "Ice Shard", "icon": "Ice Shard.png", "damage": 15, "desc": "Slows enemies"},
        {"name": "Lightning Bolt", "icon": "Lightning Bolt.png", "damage": 30, "desc": "Strikes an enemy with lightning stunning them"},
        {"name": "Minor Teleport", "icon": "Minor Teleport.png", "desc": "Blink forward instantly 100 pixels"}
    ]
}


def load_sprite_sheet_frames(sheet_path, frame_width, frame_height):
    sheet = pygame.image.load(sheet_path).convert_alpha()
    frames = {
        "down": [sheet.subsurface(pygame.Rect(i*frame_width, 0, frame_width, frame_height)) for i in range(3)],
        "left": [sheet.subsurface(pygame.Rect(i*frame_width, frame_height, frame_width, frame_height)) for i in range(3)],
        "right": [sheet.subsurface(pygame.Rect(i*frame_width, frame_height*2, frame_width, frame_height)) for i in range(3)],
        "up": [sheet.subsurface(pygame.Rect(i*frame_width, frame_height*3, frame_width, frame_height)) for i in range(3)],
    }
    return frames


class Player(pygame.sprite.Sprite):
    def __init__(self, player_id, name, player_class, x, y):
        super().__init__()
        stats = CLASS_REGISTRY[player_class]
        self.id = player_id
        self.name = name
        self.player_class = player_class

        # Store both "current" and "base" versions for recalculation
        self.base_max_hp = stats["hp"]
        self.base_max_mana = stats["mana"]
        self.base_damage = stats["damage"]
        self.base_armor = stats["armor"]
        self.base_hp_regen = 1
        self.base_mana_regen = 20

        # Derived (mutable) stats
        self.max_hp = float(self.base_max_hp)
        self.hp = float(self.base_max_hp)
        self.max_mana = float(self.base_max_mana)
        self.mana = float(self.base_max_mana)
        self.damage = float(self.base_damage)
        self.armor = float(self.base_armor)
        self.hp_regen = float(self.base_hp_regen)
        self.mana_regen = float(self.base_mana_regen)
        
        self.speed = stats["speed"]
        self.attack_speed = stats.get("attack_speed", 1.0)  # attacks per second
        self.last_attack_time = 0

        self.inventory = []
        self.equipment = {
            "Head": None,
            "Chest": None,
            "Legs": None,
            "Gloves": None
        }

        # keep both maps synchronized so saves/load and UI stay consistent
        self.equipped = self.equipment.copy()

        self.ability_objects = [None, None, None, None]

        sprite_path = os.path.join(ASSET_DIR, stats["sprite"])
        self.animations = load_sprite_sheet_frames(sprite_path, 32, 32)

        self.current_direction = "down"
        self.current_frame = 0
        self.frame_timer = 0
        self.animation_speed = 0.15
        self.image = pygame.transform.scale(
            self.animations[self.current_direction][self.current_frame], (40, 40)
        )
        self.rect = self.image.get_rect(center=(x, y))

        self.ranged = stats["attack_type"] == "ranged"
        self.range = stats.get("range", 50)

        # Spellbook & Abilities
        from abilities import create_class_abilities

        # Create Ability objects for this class
        self.spellbook = create_class_abilities(player_class)

        # Load icons
        for ability in self.spellbook:
            if hasattr(ability, "icon") and isinstance(ability.icon, str):
                icon_path = os.path.join(ASSET_DIR, ability.icon)
                ability.icon = pygame.image.load(icon_path).convert_alpha()

        # Ability quickbar (4 assignable slots)
        self.ability_objects = [None, None, None, None]

        # UI state
        self.spellbook_open = False
        self.hovered_ability = None

    # Equipment handling
    def equip_item(self, item):
        """Equip an item into its slot and recalc stats."""
        if item is None:
            print("Cannot equip item: item is None")
            return False

        slot = getattr(item, "slot", None)
        if slot is None or slot not in self.equipment:
            print(f"Cannot equip item: invalid slot ({slot})")
            return False

        # Unequip existing item in that slot
        if self.equipment.get(slot):
            self.unequip_item(slot)

        # Set in both names to keep save/load and UI consistent
        self.equipment[slot] = item
        try:
            self.equipped[slot] = item
        except Exception:
            self.equipped = self.equipment.copy()

        print(f"[DEBUG] Equipped {item.name} in {slot}")
        self.recalculate_stats()
        return True

    def unequip_item(self, slot):
        if slot not in self.equipment or not self.equipment[slot]:
            return None
        removed = self.equipment[slot]
        self.equipment[slot] = None
        # keep both attributes synchronized
        try:
            self.equipped[slot] = None
        except Exception:
            self.equipped = self.equipment.copy()
        print(f"[DEBUG] Unequipped {removed.name} from {slot}")
        self.recalculate_stats()
        return removed

    def recalculate_stats(self):
        # Start from base
        hp = self.base_max_hp
        mana = self.base_max_mana
        dmg = self.base_damage
        armor = self.base_armor
        hp_regen = self.base_hp_regen
        mana_regen = self.base_mana_regen

        percent = {"max_hp": 0, "max_mana": 0, "damage": 0, "armor": 0}

        for item in self.equipment.values():
            if not item:
                continue
            armor += item.armor
            for ench in item.enchantments:
                val = ench.get("value", 0)
                stat = ench["stat"]
                if ench["type"] == "percent":
                    percent[stat] = percent.get(stat, 0) + val
                else:
                    if stat == "hp_regen": hp_regen += val
                    elif stat == "mana_regen": mana_regen += val
                    elif stat == "damage": dmg += val

        # Apply percentage bonuses
        hp = int(hp * (1 + percent.get("max_hp", 0) / 100))
        mana = int(mana * (1 + percent.get("max_mana", 0) / 100))
        dmg = int(dmg * (1 + percent.get("damage", 0) / 100))
        armor = int(armor * (1 + percent.get("armor", 0) / 100))

        # Assign new totals
        self.max_hp = hp
        self.max_mana = mana
        self.damage = dmg
        self.armor = armor
        self.hp_regen = hp_regen
        self.mana_regen = mana_regen

        self.hp = min(self.hp, self.max_hp)
        self.mana = min(self.mana, self.max_mana)

        print(f"[DEBUG] Stats recalculated → HP:{self.max_hp} MP:{self.max_mana} DMG:{self.damage} ARM:{self.armor}")
    
    def update_regeneration(self, dt):
        # Regen rates are defined as 'points per minute'
        hp_per_second = self.hp_regen / 60.0
        mana_per_second = self.mana_regen / 60.0

        # Apply regen
        self.hp = min(self.max_hp, self.hp + hp_per_second * dt)
        self.mana = min(self.max_mana, self.mana + mana_per_second * dt)

    def update(self, dx=0, dy=0):
        if dx > 0:
            self.current_direction = "right"
        elif dx < 0:
            self.current_direction = "left"
        elif dy > 0:
            self.current_direction = "down"
        elif dy < 0:
            self.current_direction = "up"

        moving = dx != 0 or dy != 0
        if moving:
            self.frame_timer += self.animation_speed
            if self.frame_timer >= 1:
                self.frame_timer = 0
                self.current_frame = (self.current_frame + 1) % len(
                    self.animations[self.current_direction]
                )
        else:
            self.current_frame = 0

        self.image = pygame.transform.scale(
            self.animations[self.current_direction][self.current_frame], (40, 40)
        )
        self.rect.x += dx
        self.rect.y += dy

    def can_attack(self):
        now = pygame.time.get_ticks()
        return now - self.last_attack_time >= (1000 / self.attack_speed)

    def record_attack(self):
        self.last_attack_time = pygame.time.get_ticks()

    def attack(self, target):
        if self.can_attack():
            actual_damage = max(0, self.damage - getattr(target, "armor", 0))
            if hasattr(target, "take_damage"):
                target.take_damage(actual_damage)
            self.record_attack()
            return actual_damage
        return 0

    def take_damage(self, dmg, floating_group=None):
        self.hp -= dmg
        if self.hp < 0:
            self.hp = 0

        if floating_group:
            dmg_text = FloatingText(
                f"-{dmg}", self.rect.centerx, self.rect.top - 10, (255, 0, 0)
            )
            floating_group.add(dmg_text)

        return dmg


