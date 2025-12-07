import pygame
import math
import random
from playerProjectile import PlayerProjectile
from floating_text import FloatingText

# Ranger Ability Effects
def ranger_multishot(player, game):
    """Shoots 3 arrows in a spread pattern."""
    mx, my = pygame.mouse.get_pos()
    world_x = mx + (game.camera.offset_x if game.camera else 0)
    world_y = my + (game.camera.offset_y if game.camera else 0)

    base_dx = world_x - player.rect.centerx
    base_dy = world_y - player.rect.centery
    base_angle = math.atan2(base_dy, base_dx)

    for angle_offset in (-0.2, 0, 0.2):
        angle = base_angle + angle_offset
        tx = player.rect.centerx + math.cos(angle) * 300
        ty = player.rect.centery + math.sin(angle) * 300
        proj = PlayerProjectile(player, tx, ty, damage=player.damage, color=(255, 255, 0))
        game.player_projectiles.add(proj)
        game.all_sprites.add(proj)

def ranger_poison_arrow(player, game):
    """Fires a poison arrow."""
    mx, my = pygame.mouse.get_pos()
    world_x = mx + (game.camera.offset_x if game.camera else 0)
    world_y = my + (game.camera.offset_y if game.camera else 0)
    proj = PlayerProjectile(player, world_x, world_y, damage=player.damage + 5, color=(0, 200, 0))
    game.player_projectiles.add(proj)
    game.all_sprites.add(proj)

def ranger_volley(player, game):
    """Fires a rapid volley of 5 arrows."""
    mx, my = pygame.mouse.get_pos()
    world_x = mx + (game.camera.offset_x if game.camera else 0)
    world_y = my + (game.camera.offset_y if game.camera else 0)
    for i in range(5):
        proj = PlayerProjectile(player, world_x, world_y, damage=player.damage, color=(255, 150, 0))
        proj.rect.x += i * 10
        game.player_projectiles.add(proj)
        game.all_sprites.add(proj)

def ranger_evasion(player, game):
    """Temporarily boost speed."""
    player.speed_boost_timer = 180
    game.floating_texts.add(FloatingText("Evasion!", player.rect.centerx, player.rect.top, color=(50,255,50)))


# Base Ability Class
class Ability:
    def __init__(self, name, damage=0, heal=0, desc="", cooldown=2.0, mana_cost=10, effect=None):
        self.name = name
        self.damage = damage
        self.heal = heal
        self.desc = desc
        self.cooldown = cooldown
        self.mana_cost = mana_cost
        self.effect = effect
        self.last_used = 0

    def can_cast(self, now, player):
        """Check cooldown and mana"""
        return (now - self.last_used) >= self.cooldown and player.mana >= self.mana_cost

    def cast(self, player, game, now):
        """Try to cast the ability"""
        if not self.can_cast(now, player):
            return False

        player.mana -= self.mana_cost
        self.last_used = now
        game.add_floating_text(self.name, player.rect.center, color=(150, 200, 255))

        if self.effect:
            self.effect(player, game)

        return True


# Utility function to spawn projectiles
def spawn_ability_projectile(game, player, target_x, target_y, damage, speed=10, color=(255,255,255), lifetime=120, on_hit=None):
    proj = PlayerProjectile(player, target_x, target_y, damage=damage, speed=speed, color=color)
    proj.lifetime = lifetime
    if on_hit is not None:
        proj.on_hit = on_hit
    game.player_projectiles.add(proj)
    game.all_sprites.add(proj)
    return proj

# Druid abilities
def druid_entangle(player, game):
    """Roots nearby enemies."""
    for e in game.enemies:
        if math.hypot(e.rect.centerx - player.rect.centerx, e.rect.centery - player.rect.centery) < 150:
            e.status_effects.append({"type": "root", "duration": 3})
    game.add_floating_text("Entangle!", player.rect.center, (100,255,100))


def druid_healing_touch(player, game):
    """Heals the player."""
    heal_amount = 25
    player.hp = min(player.max_hp, player.hp + heal_amount)
    game.add_floating_text(f"+{heal_amount} HP", player.rect.center, (0,255,0))


def druid_natures_wrath(player, game):
    """Fires a nature beam (projectile) toward the mouse cursor."""
    mx, my = pygame.mouse.get_pos()
    if getattr(game, "camera", None):
        mx += getattr(game.camera, "offset_x", 0)
        my += getattr(game.camera, "offset_y", 0)
    spawn_ability_projectile(game, player, mx, my, damage=35, speed=14, color=(0,255,50))
    game.add_floating_text("Nature's Wrath!", player.rect.center, (0,255,50))


def druid_thorns(player, game):
    """Reflects a portion of incoming damage."""
    if not hasattr(player, "temp_buffs"):
        player.temp_buffs = []
    player.temp_buffs.append({"type": "thorns", "duration": 10, "reflect_percent": 0.3})
    game.add_floating_text("Thorns!", player.rect.center, (50,255,50))


# warrior abilities
def warrior_slash(player, game):
    """Performs a melee cone attack toward the mouse cursor."""
    mx, my = pygame.mouse.get_pos()
    if getattr(game, "camera", None):
        mx += getattr(game.camera, "offset_x", 0)
        my += getattr(game.camera, "offset_y", 0)
    px, py = player.rect.center
    base_angle = math.atan2(my - py, mx - px)
    for e in game.enemies:
        dx = e.rect.centerx - px
        dy = e.rect.centery - py
        angle_to_enemy = math.atan2(dy, dx)
        diff = abs((math.degrees(angle_to_enemy - base_angle) + 180) % 360 - 180)
        if diff < 45 and math.hypot(dx, dy) < 120:
            e.take_damage(25)
            game.add_floating_text("Slash!", e.rect.center, (255,100,100))


def warrior_shield_block(player, game):
    """Reduces incoming damage for a short duration."""
    if not hasattr(player, "temp_buffs"):
        player.temp_buffs = []
    player.temp_buffs.append({"type": "block", "duration": 5, "reduction": 0.7})
    game.add_floating_text("Shield Block!", player.rect.center, (150,150,255))


def warrior_battle_cry(player, game):
    """Temporarily increases outgoing damage."""
    if not hasattr(player, "temp_buffs"):
        player.temp_buffs = []
    player.temp_buffs.append({"type": "battlecry", "duration": 10, "damage_boost": 1.5})
    game.add_floating_text("Battle Cry!", player.rect.center, (255,150,100))


def warrior_whirlwind(player, game):
    """Spin attack hitting all nearby enemies."""
    for e in game.enemies:
        if math.hypot(e.rect.centerx - player.rect.centerx, e.rect.centery - player.rect.centery) < 150:
            e.take_damage(30)
    game.add_floating_text("Whirlwind!", player.rect.center, (255,200,200))


# witch abilities
def witch_fireball(player, game):
    """Shoots a fireball projectile toward the mouse cursor."""
    mx, my = pygame.mouse.get_pos()
    if getattr(game, "camera", None):
        mx += getattr(game.camera, "offset_x", 0)
        my += getattr(game.camera, "offset_y", 0)
    spawn_ability_projectile(game, player, mx, my, damage=25, speed=10, color=(255,100,50))
    game.add_floating_text("Fireball!", player.rect.center, (255,150,50))


def witch_ice_shard(player, game):
    """Fires an ice shard that slows on hit."""
    mx, my = pygame.mouse.get_pos()
    if getattr(game, "camera", None):
        mx += getattr(game.camera, "offset_x", 0)
        my += getattr(game.camera, "offset_y", 0)

    def slow_effect(enemy):
        enemy.status_effects.append({"type": "slow", "duration": 3, "multiplier": 0.5})

    spawn_ability_projectile(game, player, mx, my, damage=15, speed=12, color=(150,200,255), on_hit=slow_effect)
    game.add_floating_text("Ice Shard!", player.rect.center, (150,200,255))


def witch_lightning_bolt(player, game):
    """Instantly zaps a random enemy."""
    if not game.enemies:
        return
    target = random.choice(game.enemies)
    target.take_damage(30)
    target.status_effects.append({"type": "stun", "duration": 2})
    game.add_floating_text("ZAP!", target.rect.center, (255,255,100))


def witch_minor_teleport(player, game):
    """Teleports toward the mouse cursor."""
    mx, my = pygame.mouse.get_pos()
    if getattr(game, "camera", None):
        mx += getattr(game.camera, "offset_x", 0)
        my += getattr(game.camera, "offset_y", 0)

    px, py = player.rect.center
    angle = math.atan2(my - py, mx - px)
    dx = math.cos(angle) * 100
    dy = math.sin(angle) * 100
    player.rect.x += int(dx)
    player.rect.y += int(dy)
    game.add_floating_text("Blink!", player.rect.center, (200,150,255))
    
# create all abilities for a class
def create_class_abilities(class_name):
    if class_name == "Ranger":
        return [
            Ability("Multi Shot", cooldown=3, mana_cost=15, effect=ranger_multishot),
            Ability("Poison Arrow", cooldown=4, mana_cost=20, effect=ranger_poison_arrow),
            Ability("Volley", cooldown=8, mana_cost=30, effect=ranger_volley),
            Ability("Evasion", cooldown=10, mana_cost=25, effect=ranger_evasion),
        ]
    elif class_name == "Druid":
        return [
            Ability("Entangle", cooldown=6, mana_cost=25, effect=druid_entangle),
            Ability("Healing Touch", cooldown=5, mana_cost=20, effect=druid_healing_touch),
            Ability("Natures Wrath", cooldown=8, mana_cost=30, effect=druid_natures_wrath),
            Ability("Thorns", cooldown=10, mana_cost=25, effect=druid_thorns),
        ]
    elif class_name == "Warrior":
        return [
            Ability("Slash", cooldown=2, mana_cost=5, effect=warrior_slash),
            Ability("Shield Block", cooldown=10, mana_cost=15, effect=warrior_shield_block),
            Ability("Battle Cry", cooldown=12, mana_cost=20, effect=warrior_battle_cry),
            Ability("Whirlwind", cooldown=8, mana_cost=25, effect=warrior_whirlwind),
        ]
    elif class_name == "Witch":
        return [
            Ability("Fireball", cooldown=3, mana_cost=20, effect=witch_fireball),
            Ability("Ice Shard", cooldown=4, mana_cost=15, effect=witch_ice_shard),
            Ability("Lightning Bolt", cooldown=6, mana_cost=25, effect=witch_lightning_bolt),
            Ability("Minor Teleport", cooldown=8, mana_cost=10, effect=witch_minor_teleport),
        ]
    else:
        return []
