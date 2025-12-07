import pygame
import os
import random
import math
from projectile import Projectile
from floating_text import FloatingText
from playerClasses import ASSET_DIR

# Enemy registry - normal, elite, boss
ENEMY_REGISTRY = {
    # Normal Enemies
    "Skeleton Spearman": {
        "hp": 50,
        "damage": 10,
        "armor": 1,
        "speed": 1,
        "attack_speed": 0.5,
        "range": 60,
        "ranged": False,
        "sprite": "SkeletonSpearman.png",
        "category": "normal",
    },
    "Skeleton Archer": {
        "hp": 40,
        "damage": 6,
        "armor": 1,
        "speed": 2,
        "attack_speed": 1.0,
        "range": 200,
        "ranged": True,
        "sprite": "SkeletonArcher.png",
        "category": "normal",
    },

    # Elite enemies
    "Skeleton Knight": {
        "hp": 120,
        "damage": 20,
        "armor": 8,
        "speed": 1,
        "attack_speed": 0.7,
        "range": 55,
        "ranged": False,
        "sprite": "SkeletonKnight.png",
        "category": "elite",
    },
    "Skeleton Mage": {
        "hp": 35,
        "damage": 15,
        "armor": 4,
        "speed": 2,
        "attack_speed": 0.4,
        "range": 300,
        "ranged": True,
        "sprite": "SkeletonMage.png",
        "category": "elite",
    },

    # boss enemies
    "The Dark Wizard": {
        "hp": 400,
        "damage": 30,
        "armor": 10,
        "speed": 3,
        "attack_speed": 0.2,
        "range": 300,
        "ranged": True,
        "sprite": "bossSheet.png",
        "category": "boss",
        "frame_w": 96,
        "frame_h": 96,
        "sheet_rows": 4,
        "sheet_cols": 3,
        "sheet_row": 1,        
        "draw_size": (96, 96),
    },
    "Lord Invocatus": {
        "hp": 600,
        "damage": 25,
        "armor": 15,
        "speed": 3.5,
        "attack_speed": 0.5,
        "range": 150,
        "ranged": False,
        "sprite": "bossSheet.png",
        "category": "boss",
        "frame_w": 96,
        "frame_h": 96,
        "sheet_rows": 4,
        "sheet_cols": 3,
        "sheet_row": 0,        
        "draw_size": (96, 96),
    },
        "Eye of the Shadows": {
        "hp": 350,
        "damage": 40,
        "armor": 14,
        "speed": 3,
        "attack_speed": 0.2,
        "range": 600,
        "ranged": True,
        "sprite": "bossSheet.png",
        "category": "boss",
        "frame_w": 96,
        "frame_h": 96,
        "sheet_rows": 4,
        "sheet_cols": 3,
        "sheet_row": 2,        
        "draw_size": (96, 96),
    },
        "Sohl, the Last Dragon": {
        "hp": 800,
        "damage": 75,
        "armor": 20,
        "speed": 2.5,
        "attack_speed": 0.2,
        "range": 200,
        "ranged": False,
        "sprite": "bossSheet.png",
        "category": "boss",
        "frame_w": 96,
        "frame_h": 96,
        "sheet_rows": 4,
        "sheet_cols": 3,
        "sheet_row": 3,        
        "draw_size": (128, 128),
    },
}

# Configuration
ENEMY_DENSITY = 100
MIN_ENEMIES = 0
MAX_ENEMIES = 10
MAX_ELITES_PER_ROOM = 3
MAX_BOSS_PER_DUNGEON = 1

DIFFICULTY_MULTIPLIERS = {
    "easy": 0.5,
    "normal": 1.0,
    "hard": 1.5,
    "legendary": 2.0,
}

# Sprite loader
def load_sprite_sheet_frames(sheet_path, frame_w=32, frame_h=32, rows=4, cols=3, selected_row=None):
    # Loads frames from a sprite sheet
    sheet = pygame.image.load(sheet_path).convert_alpha()
    frames = {"down": [], "left": [], "right": [], "up": []}
    sw, sh = sheet.get_size()

    def read_row(row_idx):
        row_frames = []
        for c in range(cols):
            fx = c * frame_w
            fy = row_idx * frame_h
            if fx + frame_w <= sw and fy + frame_h <= sh:
                sub = sheet.subsurface(pygame.Rect(fx, fy, frame_w, frame_h)).copy()
                row_frames.append(sub)
        return row_frames

    if selected_row is not None:
        selected_row = max(0, min(rows - 1, int(selected_row)))
        row_frames = read_row(selected_row)
        for key in frames:
            frames[key] = row_frames.copy()
    else:
        for r in range(rows):
            row_frames = read_row(r)
            if r == 0: frames["down"] = row_frames
            elif r == 1: frames["left"] = row_frames
            elif r == 2: frames["right"] = row_frames
            elif r == 3: frames["up"] = row_frames

    return frames

# Enemy class
class Enemy(pygame.sprite.Sprite):
    def __init__(self, enemy_type, x, y, difficulty="normal"):
        super().__init__()
        stats = ENEMY_REGISTRY[enemy_type]

        # Basic stats
        mult = DIFFICULTY_MULTIPLIERS.get(difficulty, 1.0)
        self.type = enemy_type
        self.category = stats.get("category", "normal")
        self.hp = int(stats["hp"] * mult)
        self.max_hp = int(stats["hp"] * mult)
        self.damage = int(stats["damage"] * mult)
        self.armor = stats.get("armor", 0)
        self.speed = stats.get("speed", 1)
        self.attack_speed = stats.get("attack_speed", 1.0)
        self.range = stats.get("range", 40)
        self.ranged = stats.get("ranged", False)
        self.is_enemy = True
        self.last_attack_time = 0
        self.last_damage = 0

        # Frame setup
        frame_w = stats.get("frame_w", 32)
        frame_h = stats.get("frame_h", 32)
        rows = stats.get("sheet_rows", 4)
        cols = stats.get("sheet_cols", 3)
        selected_row = stats.get("sheet_row", None)
        draw_size = stats.get("draw_size", None)

        sprite_path = os.path.join(ASSET_DIR, stats["sprite"])

        try:
            self.animations = load_sprite_sheet_frames(sprite_path, frame_w, frame_h, rows, cols, selected_row)
        except Exception as e:
            print(f"⚠️ Failed to load sprite sheet {sprite_path}: {e}")
            dummy = pygame.Surface((frame_w, frame_h), pygame.SRCALPHA)
            self.animations = {"down": [dummy], "left": [dummy], "right": [dummy], "up": [dummy]}

        # Validate frames
        for direction, frames in list(self.animations.items()):
            valid = [f for f in frames if pygame.mask.from_surface(f).count() > 0]
            if not valid:
                print(f"⚠️ Enemy '{enemy_type}' missing valid frames for '{direction}'")
                del self.animations[direction]
            else:
                self.animations[direction] = valid
        if not self.animations:
            raise ValueError(f"Enemy '{enemy_type}' has no valid frames — check sprite sheet path: {sprite_path}")

        # Animation state
        self.current_direction = "down" if "down" in self.animations else next(iter(self.animations))
        self.current_frame = 0
        self.frame_timer = 0
        self.animation_speed = stats.get("animation_speed", 0.12)

        # Determine draw size
        if draw_size:
            dw, dh = draw_size
        elif self.category == "boss":
            dw, dh = 96, 96
        else:
            dw, dh = 40, 40

        # Initial image
        frame = self.animations[self.current_direction][self.current_frame]
        self.image = pygame.transform.scale(frame, (int(dw), int(dh)))
        self.rect = self.image.get_rect(center=(x, y))

        print(f"[DEBUG] Spawned Enemy: {self.type} ({self.category}) at {x,y} draw={dw}x{dh}")

    # Update + Animate
    def update(self, *args):
        self.frame_timer += self.animation_speed
        if self.frame_timer >= 1:
            self.frame_timer = 0
            self.current_frame = (self.current_frame + 1) % len(self.animations[self.current_direction])
            frame = self.animations[self.current_direction][self.current_frame]
            self.image = pygame.transform.scale(frame, self.image.get_size())

    # Movement and Animation
    def move_and_animate(self, dx, dy, walls, player=None):
        if self.ranged and player:
            px, py = player.rect.center
            ex, ey = self.rect.center
            dist = math.hypot(px - ex, py - ey)
            if dist > 0:
                if dist <= self.range:
                    # Stop moving when inside attack range so ranged enemies can fire
                    dx, dy = 0, 0
                else:
                    # Move toward player if out of range
                    dx, dy = (px - ex) / dist * self.speed, (py - ey) / dist * self.speed

        self.rect.x += dx
        for wall in walls:
            if self.rect.colliderect(wall.rect):
                if dx > 0: self.rect.right = wall.rect.left
                elif dx < 0: self.rect.left = wall.rect.right

        self.rect.y += dy
        for wall in walls:
            if self.rect.colliderect(wall.rect):
                if dy > 0: self.rect.bottom = wall.rect.top
                elif dy < 0: self.rect.top = wall.rect.bottom

        if abs(dx) > abs(dy):
            self.current_direction = "right" if dx > 0 else "left"
        elif abs(dy) > 0:
            self.current_direction = "down" if dy > 0 else "up"

        moving = dx != 0 or dy != 0
        if moving:
            self.frame_timer += self.animation_speed
            if self.frame_timer >= 1:
                self.frame_timer = 0
                self.current_frame = (self.current_frame + 1) % len(self.animations[self.current_direction])
        else:
            self.current_frame = 0

        self.image = pygame.transform.scale(
            self.animations[self.current_direction][self.current_frame],
            self.image.get_size()
        )

    # Attack logic
    def can_attack(self):
        now = pygame.time.get_ticks()
        return now - self.last_attack_time >= (1000 / self.attack_speed)

    def record_attack(self):
        self.last_attack_time = pygame.time.get_ticks()

    def attack(self, target, projectile_group=None, floating_group=None):
        if not self.can_attack():
            return 0

        dx = target.rect.centerx - self.rect.centerx
        dy = target.rect.centery - self.rect.centery
        dist = math.hypot(dx, dy)

        if self.ranged and projectile_group and dist <= self.range:
            # Create projectile for ranged enemies
            proj = Projectile(self.rect.centerx, self.rect.centery, target, self.damage,
                              floating_group=floating_group,
                              color=(255, 100, 100),  # Red color for enemy projectiles
                              speed=8)  # Slightly slower than player projectiles
            projectile_group.add(proj)

            # Try to add projectile to the game's all_sprites if available
            for group in self.groups():
                game = getattr(group, 'game', None)
                if game and hasattr(game, 'all_sprites'):
                    game.all_sprites.add(proj)
                    break

            actual_damage = 0
        elif not self.ranged and dist <= self.range:
            actual_damage = max(0, self.damage - getattr(target, "armor", 0))
            if hasattr(target, "take_damage"):
                target.take_damage(actual_damage, floating_group)
                # Debug logging for melee hits
                print(f"[ENEMY HIT] {self.type} hit target for {actual_damage}")
        else:
            actual_damage = 0

        self.record_attack()
        return actual_damage

    # Damage handling
    def take_damage(self, dmg, sprite_group=None):
        self.hp = max(0, self.hp - dmg)
        if sprite_group:
            dmg_text = FloatingText(f"-{dmg}", self.rect.centerx, self.rect.top - 10, (255, 50, 50))
            sprite_group.add(dmg_text)
        return dmg

    # health bar
    def draw_stats(self, surface):
        font = pygame.font.SysFont("Arial", 18)
        label = font.render(f"{self.type} HP:{self.hp}/{self.max_hp}", True, (255, 0, 0))
        surface.blit(label, (self.rect.x, self.rect.y - 20))

# spawn logic
def spawn_enemies_for_dungeon(room_data, difficulty="normal"):
    enemies = pygame.sprite.Group()
    all_rooms = list(room_data.keys())
    if not all_rooms:
        print("[DEBUG] No rooms to spawn enemies.")
        return enemies

    boss_room = random.choice(all_rooms)
    boss_spawned = False
    print(f"[DEBUG] Boss room selected: {boss_room}")

    normal_types = [k for k, v in ENEMY_REGISTRY.items() if v["category"] == "normal"]
    elite_types = [k for k, v in ENEMY_REGISTRY.items() if v["category"] == "elite"]
    boss_types = [k for k, v in ENEMY_REGISTRY.items() if v["category"] == "boss"]

    for coords, room_rect in room_data.items():
        rx, ry = coords
        if coords == boss_room and not boss_spawned:
            boss_type = random.choice(boss_types)
            bx = room_rect.left + room_rect.width // 2
            by = room_rect.top + room_rect.height // 2
            boss = Enemy(boss_type, bx, by, difficulty)
            enemies.add(boss)
            boss_spawned = True
            print(f"[DEBUG] Spawned BOSS '{boss_type}' in room {coords}")
            continue

        num_normals = random.randint(2, 6)
        num_elites = random.randint(0, MAX_ELITES_PER_ROOM)
        print(f"[DEBUG] Room {coords}: {num_normals} normals, {num_elites} elites")

        for _ in range(num_normals):
            e_type = random.choice(normal_types)
            x = random.randint(room_rect.left + 64, room_rect.right - 64)
            y = random.randint(room_rect.top + 64, room_rect.bottom - 64)
            enemies.add(Enemy(e_type, x, y, difficulty))

        for _ in range(num_elites):
            e_type = random.choice(elite_types)
            x = random.randint(room_rect.left + 64, room_rect.right - 64)
            y = random.randint(room_rect.top + 64, room_rect.bottom - 64)
            enemies.add(Enemy(e_type, x, y, difficulty))

    print(f"[DEBUG] Total enemies spawned: {len(enemies)}")
    return enemies