import random
import pygame
import math
from floating_text import FloatingText
from enemy import ENEMY_REGISTRY

# Rarity setup
RARITY_COLORS = {
    "Normal": (255, 255, 255),   # White
    "Magic": (100, 100, 255),    # Blue
    "Rare": (255, 255, 100),     # Yellow
    "Epic": (200, 100, 255),     # Purple
    "Legendary": (255, 150, 50), # Orange
}

RARITY_ENCHANTMENTS = {
    "Normal": 0,
    "Magic": 1,
    "Rare": 2,
    "Epic": 3,
    "Legendary": 4
}

RARITY_BY_ENCHANTS = {
    0: "Normal",
    1: "Magic",
    2: "Rare",
    3: "Epic",
    4: "Legendary"
}

RARITY_WEIGHTS = {
    "Normal": 40,
    "Magic": 35,
    "Rare": 15,
    "Epic": 7,
    "Legendary": 3
}

# Enchantments
ENCHANTMENT_POOL = [
    {"name": "Bonus Health %", "type": "percent", "stat": "max_hp", "min": 1, "max": 15},
    {"name": "Bonus Mana %", "type": "percent", "stat": "max_mana", "min": 1, "max": 15},
    {"name": "Health Regen", "type": "flat", "stat": "hp_regen", "min": 1, "max": 10},
    {"name": "Mana Regen", "type": "flat", "stat": "mana_regen", "min": 1, "max": 10},
    {"name": "Bonus Damage %", "type": "percent", "stat": "damage", "min": 1, "max": 15},
    {"name": "Bonus Armor %", "type": "percent", "stat": "armor", "min": 1, "max": 15},
]

EQUIP_SLOTS = ["Head", "Chest", "Legs", "Gloves"]

# Item class
class Item:
    def __init__(self, slot, name=None, rarity=None, armor=None, enchantments=None):
        self.slot = slot
        self.rarity = rarity or self.generate_rarity()
        self.enchantments = enchantments or self.generate_enchantments()
        for ench in self.enchantments:
            if "value" not in ench:
                ench["value"] = random.randint(ench["min"], ench["max"])
        self.armor = armor if armor is not None else random.randint(5, 25)
        self.name = name or f"{self.rarity} {self.slot}"
        self.color = RARITY_COLORS[self.rarity]

    def generate_rarity(self):
        rarities = list(RARITY_WEIGHTS.keys())
        weights = list(RARITY_WEIGHTS.values())
        return random.choices(rarities, weights=weights, k=1)[0]

    def generate_enchantments(self):
        num = RARITY_ENCHANTMENTS[self.rarity]
        if num == 0:
            return []
        return random.sample(ENCHANTMENT_POOL, num)

    def describe(self):
        desc = [f"{self.name} [{self.rarity}] (Armor: {self.armor})"]
        for ench in self.enchantments:
            sign = "%" if ench["type"] == "percent" else ""
            desc.append(f" +{ench['value']}{sign} {ench['name']}")
        return "\n".join(desc)


# Item Generation
def generate_random_item(rarity_multiplier=1.0):
    rarities = ["Normal", "Magic", "Rare", "Epic", "Legendary"]
    base_weights = [70, 20, 7, 2, 1]

    # Adjust rarity weights by difficulty multiplier
    adjusted_weights = [
        max(1, int(w / (rarity_multiplier ** (i * 0.5)))) for i, w in enumerate(base_weights)
    ]

    rarity = random.choices(rarities, weights=adjusted_weights, k=1)[0]

    # Random slot and base armor scaling
    slot = random.choice(EQUIP_SLOTS)
    base_armor = {
        "Normal": random.randint(1, 3),
        "Magic": random.randint(4, 6),
        "Rare": random.randint(7, 9),
        "Epic": random.randint(10, 13),
        "Legendary": random.randint(14, 18),
    }[rarity]

    # Generate enchantments according to rarity
    num_enchants = RARITY_ENCHANTMENTS[rarity]
    enchantments = random.sample(ENCHANTMENT_POOL, num_enchants)
    for ench in enchantments:
        ench["value"] = random.randint(ench["min"], ench["max"])

    name = f"{rarity} {slot}"
    return Item(slot=slot, name=name, rarity=rarity, armor=base_armor, enchantments=enchantments)


# Loot Drop Function
def drop_loot(enemy, game):
    """Drops loot based on enemy category and dungeon difficulty."""
    category = getattr(enemy, "category", "normal")

    base = {
        "normal": (0.10, (1, 1)),
        "elite": (0.30, (1, 1)),
        "boss": (0.50, (1, 4)),
    }
    drop_chance, (min_rolls, max_rolls) = base.get(category, base["normal"])

    difficulty = getattr(game, "difficulty", "normal").lower()
    diff_mods = {
        "easy": {"chance_mult": 0.8, "rarity_mult": 0.8},
        "normal": {"chance_mult": 1.0, "rarity_mult": 1.0},
        "hard": {"chance_mult": 1.3, "rarity_mult": 1.5},
        "legendary": {"chance_mult": 1.6, "rarity_mult": 2.0},
    }
    mods = diff_mods.get(difficulty, diff_mods["normal"])

    drop_chance *= mods["chance_mult"]
    rolls = random.randint(min_rolls, max_rolls)
    dropped_any = False

    for _ in range(rolls):
        if random.random() <= drop_chance:
            item = generate_random_item(rarity_multiplier=mods["rarity_mult"])
            ox, oy = random.randint(-12, 12), random.randint(-12, 12)
            drop = LootDrop(item, enemy.rect.centerx + ox, enemy.rect.centery + oy)

            if not hasattr(game, "loot_drops"):
                game.loot_drops = pygame.sprite.Group()
            if not hasattr(game, "all_sprites"):
                game.all_sprites = pygame.sprite.Group()

            game.loot_drops.add(drop)
            game.all_sprites.add(drop)
            dropped_any = True

            print(f"[DEBUG] {difficulty.title()} {category} dropped {item.name} ({item.rarity})")

    if not dropped_any:
        print(f"[DEBUG] No drops from {category} ({difficulty})")


# Loot Drop Sprite
class LootDrop(pygame.sprite.Sprite):
    def __init__(self, item, x, y):
        super().__init__()
        self.item = item

        # Create a colored "glow" for rarity
        glow = pygame.Surface((30, 30), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*item.color, 120), (15, 15), 15)

        core = pygame.Surface((14, 14))
        core.fill(item.color)

        self.image = pygame.Surface((30, 30), pygame.SRCALPHA)
        self.image.blit(glow, (0, 0))
        self.image.blit(core, (8, 8))

        self.rect = self.image.get_rect(center=(x, y))
        self.float_y = 0

    def update(self):
        self.float_y += 0.1
        self.rect.y += int(1.5 * math.sin(self.float_y))

    def pickup(self, player):
        player.inventory.append(self.item)
        game = getattr(player, "game", None)
        if game and hasattr(game, "floating_texts"):
            game.floating_texts.add(
                FloatingText(f"Picked up {self.item.name}", player.rect.centerx, player.rect.top - 20, self.item.color)
            )
        self.kill()
