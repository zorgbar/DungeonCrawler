import pygame
import random
import math
import os
import sys
import json
from playerClasses import Player, CLASS_REGISTRY, CLASS_ABILITIES
from dungeonGenerator import Dungeon
from camera import Camera
from door import Door
from enemy import Enemy, ENEMY_REGISTRY
from floating_text import FloatingText
from playerProjectile import PlayerProjectile
from abilities import create_class_abilities
from items import Item, EQUIP_SLOTS, RARITY_COLORS
from soundManager import SoundManager

# Config
TILE_SIZE = 32
ROOM_W, ROOM_H = 40, 30

# Inventory UI config
INV_ROWS = 5
INV_COLS = 6
SLOT_SIZE = 64
INV_MARGIN = 10
EQUIP_SLOTS_UI = ["Head", "Chest", "Legs", "Gloves"]

# Game states
state_Menu = "menu"
state_CharSelect = "charSelect"
state_Settings = "settings"
state_Hub = "hub"
state_DungeonSelect = "dungeonselect"
state_Dungeon = "dungeon"
state_Dead = "player_dead"
state_Pause = "pause"
state_CharManage = "CHAR_MANAGE"   # character management screen
state_CharCreate = "CHAR_CREATE"   # create new character
state_LoadSelect = "LOAD_SELECT"   # choose saved character
state_Shop = "shop"
state_Healer = "healer"

ASSET_DIR = "assets"  # assests folder

# Utility

def safe_load(path, convert_alpha=True):
    """Load an image safely, return None if failure (and print debug)."""
    try:
        surf = pygame.image.load(path)
        return surf.convert_alpha() if convert_alpha else surf.convert()
    except Exception as e:
        print(f"⚠️  Failed loading image '{path}': {e}")
        return None

def int_rect_from(fx, fy, fw, fh):
    """Return integer rect (avoids fractional subsurface problems)."""
    return pygame.Rect(int(round(fx)), int(round(fy)), int(round(fw)), int(round(fh)))

# Core Game code

class Game:
    def __init__(self):
        pygame.init()
        pygame.mixer.init()
        os.makedirs("saves", exist_ok=True)
        # keep track of visited dungeon rooms (set of (rx, ry))
        self.visited_rooms = set()
        # hub NPC sprites
        self.shop_img = safe_load(os.path.join(ASSET_DIR, "shopkeeper.png"))
        self.healer_img = safe_load(os.path.join(ASSET_DIR, "healer.png"))

        # Initialize sprite groups
        self.all_sprites = pygame.sprite.Group()
        self.player_projectiles = pygame.sprite.Group()
        self.enemy_projectiles = pygame.sprite.Group() 
        self.enemies = pygame.sprite.Group()
        self.walls = pygame.sprite.Group()
        self.floating_texts = pygame.sprite.Group()

        self.settings = {
            "resolution": (1280, 720),
            "fullscreen": False
        }
        self.screen = pygame.display.set_mode(self.settings["resolution"])
        pygame.display.set_caption("Dungeon Crawler")
        self.clock = pygame.time.Clock()
        self.running = True

        self.sounds = SoundManager()

        self.menu_options = ["Play", "Settings", "Quit"]
        self.selected_menu_index = 0
        self.settings_options = ["Music Volume", "SFX Volume", "Back"]
        self.selected_settings_index = 0
        # Default resolution and fullscreen settings
        self.available_resolutions = [
            (1280, 720),
            (1600, 900),
            (1920, 1080)
        ]
        self.current_resolution_index = 0
        self.fullscreen = False

        # Store current settings for audio and resolution
        self.settings_options = ["Resolution", "Fullscreen", "Music Volume", "SFX Volume", "Back"]

        self.selected_settings_index = 0



        self.music_volume = 0.5
        self.sfx_volume = 0.7

        # Load sound effects
        self.sounds.load("attack", "assets/sounds/attack.wav", 0.6)
        self.sounds.load("hit", "assets/sounds/hit.wav", 0.6)
        self.sounds.load("loot", "assets/sounds/loot.wav", 0.7)
        self.sounds.load("death", "assets/sounds/death.wav", 0.7)

        # Start background music
        self.sounds.play_music("assets/music/dungeon_theme.mp3", volume=0.4)

        # Core state
        self.state = state_Menu
        self.difficulty = "easy"
    
        # Player / sprites
        self.player = None
        
        # UI / controls
        self.selected_ability = 0
        self.spellbook_open = False
        self.controls_p1 = {"up": pygame.K_w, "down": pygame.K_s, "left": pygame.K_a, "right": pygame.K_d}

        # Dungeon / rooms
        self.dungeon = None
        self.current_room = None
        self.room_sizes = {}
        self.room_walls = {}
        self.room_doors = {}
        self.room_enemies = {}
        self.room_floors = {}                
        self.room_horiz_walls_textures = {}  # (rx,ry) -> list of frames used for horizontal walls (merged pair)
        self.room_horiz_wall_map = {}        
        self.corner_tex = safe_load(os.path.join(ASSET_DIR, "corner.png"))

        # Camera and hub
        self.camera = None
        self.hub_cam_x = 0
        self.hub_cam_y = 0

        # Asset loading: floor sheets
        self.floor_sheets = []
        for i in range(1, 4):
            p = os.path.join(ASSET_DIR, f"floor{i}.png")
            s = safe_load(p)
            if s:
                self.floor_sheets.append(s)
            else:
                print(f"DEBUG: floor sheet missing: {p}")

        # Vertical wall texture (single)
        vt = safe_load(os.path.join(ASSET_DIR, "wall_vertical.png"))
        if vt:
            # small scale tweak 
            self.wall_textures = {"vertical": pygame.transform.scale(vt, (30, vt.get_height()))}
        else:
            self.wall_textures = {"vertical": pygame.Surface((30, 76), pygame.SRCALPHA)}
            self.wall_textures["vertical"].fill((120, 80, 40))
            print("DEBUG: fallback vertical wall texture used")

        # Horizontal wall sheets
        self.horiz_wall_sheets = []
        for i in range(1, 5):
            p = os.path.join(ASSET_DIR, f"hwall{i}.png")
            s = safe_load(p)
            if s:
                self.horiz_wall_sheets.append(s)
            else:
                print(f"DEBUG: missing horizontal wall sheet: {p}")
        if len(self.horiz_wall_sheets) < 4:
            # Fill with dummy surfaces to avoid index errors
            while len(self.horiz_wall_sheets) < 4:
                surf = pygame.Surface((100, 74), pygame.SRCALPHA)
                surf.fill((100, 100, 100))
                self.horiz_wall_sheets.append(surf)

        # Spellbook/abilities / classes
        self.class_list = list(CLASS_REGISTRY.keys())
        self.selected_index = 0

        # Hub geometry
        self.walls = pygame.sprite.Group()
        self.interactables = []
        self.create_hub()

        # Door cooldown to avoid immediate teleport back
        self.door_cooldown = 2.0  # seconds

        print("DEBUG: Game initialized")
        self.loot_drops = pygame.sprite.Group()
        # Shop/healer UI state
        self.shop_selected_index = 0
        self.shop_mode = "sell"  # "sell" or "buy" (buy uses number keys)
        self.healer_confirm = False
    def load_sounds(self):
        self.sounds.load("attack", "attack.wav", 0.6)
        self.sounds.load("pickup", "pickup.wav", 0.7)
        self.sounds.load("hit", "hit.wav", 0.7)
        self.sounds.load("death", "death.wav", 0.8)
        self.sounds.load("equip", "equip.ogg", 0.7)
        self.sounds.load("heal", "heal.wav", 0.5)    

    def apply_resolution(self):
        # Recreate the game window using the current resolution and fullscreen state
        res = self.available_resolutions[self.current_resolution_index]
        flags = pygame.FULLSCREEN if self.fullscreen else 0
        self.screen = pygame.display.set_mode(res, flags)
        pygame.display.set_caption("GameDevAlphaV3")

    def add_floating_text(self, text, pos, color=(255, 255, 255)):
        # Creates a floating text object (like damage numbers or ability names)
        if hasattr(self, "floating_texts"):
            x, y = pos
            ft = FloatingText(text, x, y, color)
            self.floating_texts.add(ft)
            self.all_sprites.add(ft)

    def cast_projectile_ability(self, player, damage, speed, color, lifetime=120, on_hit=None):
        # Spawn an ability projectile toward the mouse cursor
        mx, my = pygame.mouse.get_pos()
        world_x = mx + (self.camera.offset_x if self.camera else 0)
        world_y = my + (self.camera.offset_y if self.camera else 0)

        proj = PlayerProjectile(player, world_x, world_y, damage, speed, color)
        proj.lifetime = lifetime

        proj.on_hit = on_hit

        self.player_projectiles.add(proj)
        self.all_sprites.add(proj)
        return proj

    # Hub utils
    def create_hub(self):
        self.walls.empty()
        self.interactables.clear()
        width, height = self.screen.get_size()
        for x in range(0, width, TILE_SIZE):
            self.add_wall(x, 0)
            self.add_wall(x, height - TILE_SIZE)
        for y in range(0, height, TILE_SIZE):
            self.add_wall(0, y)
            self.add_wall(width - TILE_SIZE, y)
        # a few interior walls
        self.add_wall(120, 120, 160, 120)
        self.add_wall(width - 360, 120, 160, 120)
        self.add_wall(120, height - 280, 160, 120)
        gate_w, gate_h = 160, 120
        gate_x = (width // 2) + 120
        gate_y = (height // 2) - (gate_h // 2)
        gate_rect = pygame.Rect(gate_x, gate_y, gate_w, gate_h)
        self.interactables.append({"rect": gate_rect, "type": "dungeon"})
        # Add shop NPC and healer NPC interactable rects
        shop_rect = pygame.Rect(100, height//2 - 64, 120, 120)
        healer_rect = pygame.Rect(width - 240, height//2 - 64, 120, 120)
        self.interactables.append({"rect": shop_rect, "type": "shop"})
        self.interactables.append({"rect": healer_rect, "type": "healer"})

    def add_wall(self, x, y, w=TILE_SIZE, h=TILE_SIZE, wall_type="vertical"):
        s = pygame.sprite.Sprite()
        s.image = pygame.Surface((w, h), pygame.SRCALPHA)
        s.image.fill((100, 60, 30))
        s.rect = s.image.get_rect(topleft=(x, y))
        s.wall_type = wall_type
        self.walls.add(s)

    # Main loop / events
    def run(self):
        while self.running:
            self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(60)

    def handle_events(self):
        for ev in pygame.event.get():
            # Ensure ESC closes UIs (shop / healer) before any other handlers run
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                if self.state in (state_Shop, state_Healer):
                    self.state = state_Hub
                    # consume the event and skip further handling for this event
                    continue

            # Handle shop buy keys early so other branches don't skip them
            if ev.type == pygame.KEYDOWN and self.state == state_Shop:
                try:
                    key_to_index = {
                        pygame.K_1: 0, pygame.K_2: 1, pygame.K_3: 2, pygame.K_4: 3, pygame.K_5: 4,
                        pygame.K_KP1: 0, pygame.K_KP2: 1, pygame.K_KP3: 2, pygame.K_KP4: 3, pygame.K_KP5: 4
                    }
                    if ev.key in key_to_index:
                        rarities = ["Normal", "Magic", "Rare", "Epic", "Legendary"]
                        idx = key_to_index[ev.key]
                        rar = rarities[idx] if idx < len(rarities) else rarities[0]
                        self.buy_item_by_rarity(rar)
                        # consume this event
                        continue
                except Exception:
                    pass

            # Handle shop sell clicks early so other branches don't skip them
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and self.state == state_Shop:
                try:
                    pos = ev.pos
                    for rect, idx in getattr(self, "_shop_item_rects", []):
                        if rect.collidepoint(pos):
                            self.sell_selected_item(idx)
                            self.shop_selected_index = min(self.shop_selected_index, max(0, len(getattr(self.player, "inventory", [])) - 1))
                            break
                except Exception:
                    pass
                continue

            if ev.type == pygame.QUIT:
                self.running = False

            if ev.type == pygame.KEYDOWN:

                # pause menu
                if ev.key == pygame.K_ESCAPE:
                    # Open Pause Menu if in active gameplay
                    if self.state in (state_Hub, state_Dungeon):
                        self.previous_state = self.state
                        self.state = state_Pause
                        self.pause_options = ["Save Game", "Settings", "Quit to Menu", "Resume"]
                        self.selected_pause_index = 0
                        return  # Stop processing other input this frame

                    # Close Pause Menu
                    elif self.state == state_Pause:
                        self.state = getattr(self, "previous_state", state_Hub)
                        return

                # MAIN MENU
                if self.state == state_Menu:
                    if ev.key == pygame.K_UP:
                        self.selected_menu_index = (self.selected_menu_index - 1) % len(self.menu_options)
                    elif ev.key == pygame.K_DOWN:
                        self.selected_menu_index = (self.selected_menu_index + 1) % len(self.menu_options)
                    elif ev.key == pygame.K_RETURN:
                        choice = self.menu_options[self.selected_menu_index]
                        if choice == "Play":
                            self.state = state_CharManage
                        elif choice == "Settings":
                            self.state = state_Settings
                        elif choice == "Quit":
                            pygame.quit()
                            sys.exit()

                # SETTINGS MENU
                elif self.state == state_Settings:
                    if ev.key == pygame.K_UP:
                        self.selected_settings_index = (self.selected_settings_index - 1) % len(self.settings_options)
                    elif ev.key == pygame.K_DOWN:
                        self.selected_settings_index = (self.selected_settings_index + 1) % len(self.settings_options)

                    elif ev.key == pygame.K_LEFT:
                        option = self.settings_options[self.selected_settings_index]
                        if option == "Music Volume":
                            self.music_volume = max(0.0, self.music_volume - 0.1)
                            pygame.mixer.music.set_volume(self.music_volume)
                        elif option == "SFX Volume":
                            self.sfx_volume = max(0.0, self.sfx_volume - 0.1)
                        elif option == "Resolution":
                            self.current_resolution_index = (self.current_resolution_index - 1) % len(self.available_resolutions)
                            self.apply_resolution()

                    elif ev.key == pygame.K_RIGHT:
                        option = self.settings_options[self.selected_settings_index]
                        if option == "Music Volume":
                            self.music_volume = min(1.0, self.music_volume + 0.1)
                            pygame.mixer.music.set_volume(self.music_volume)
                        elif option == "SFX Volume":
                            self.sfx_volume = min(1.0, self.sfx_volume + 0.1)
                        elif option == "Resolution":
                            self.current_resolution_index = (self.current_resolution_index + 1) % len(self.available_resolutions)
                            self.apply_resolution()

                    elif ev.key == pygame.K_RETURN:
                        option = self.settings_options[self.selected_settings_index]
                        if option == "Fullscreen":
                            self.fullscreen = not self.fullscreen
                            self.apply_resolution()
                        elif option == "Back":
                            self.state = state_Menu

                # pause menu
                elif self.state == state_Pause:
                    if ev.key == pygame.K_UP:
                        self.selected_pause_index = (self.selected_pause_index - 1) % len(self.pause_options)
                    elif ev.key == pygame.K_DOWN:
                        self.selected_pause_index = (self.selected_pause_index + 1) % len(self.pause_options)
                    elif ev.key == pygame.K_RETURN:
                        option = self.pause_options[self.selected_pause_index]

                        if option == "Save Game":
                            self.save_game()

                        elif option == "Settings":
                            self.state = state_Settings
                            self.selected_settings_index = 0

                        elif option == "Quit to Menu":
                            # Reset everything and return to main menu
                            self.state = state_Menu
                            self.all_sprites.empty()
                            self.enemies.empty()
                            self.enemy_projectiles.empty()
                            self.player_projectiles.empty()
                            self.floating_texts.empty()
                            self.player = None

                        elif option == "Resume":
                            self.state = getattr(self, "previous_state", state_Hub)

                    return  # prevent fallthrough to other states  
       
                # character select
                elif self.state == state_CharManage:
                    if ev.key == pygame.K_UP:
                        self.selected_index = (self.selected_index - 1) % 2
                    elif ev.key == pygame.K_DOWN:
                        self.selected_index = (self.selected_index + 1) % 2
                    elif ev.key == pygame.K_RETURN:
                        if self.selected_index == 0:
                            # Create new character
                            self.selected_class_index = 0
                            self.char_name = ""
                            self.state = state_CharCreate
                        else:
                            # Load existing character
                            # Hide meta files (foo_meta.json)
                            self.load_files = sorted(
                                list({f[:-5] for f in os.listdir("saves")
                                      if f.endswith(".json") and not f.endswith("_meta.json")})
                            )
                            if not self.load_files:
                                print("No saved characters found.")
                                return
                            self.selected_load_index = 0
                            self.state = state_LoadSelect
                    elif ev.key == pygame.K_ESCAPE:
                        self.state = state_Menu
                elif self.state == state_CharCreate:
                    if ev.key == pygame.K_UP:
                        self.selected_class_index = (self.selected_class_index - 1) % len(self.class_list)
                    elif ev.key == pygame.K_DOWN:
                        self.selected_class_index = (self.selected_class_index + 1) % len(self.class_list)
                    elif ev.key == pygame.K_RETURN:
                        if self.char_name.strip():
                            cls = self.class_list[self.selected_class_index]
                            cx, cy = self.screen.get_width() // 2, self.screen.get_height() // 2
                            self.spawn_player(cls, cx, cy, name=self.char_name.strip())
                            self.save_character()
                            self.state = state_Hub
                    elif ev.key == pygame.K_BACKSPACE:
                        self.char_name = self.char_name[:-1]
                    elif ev.unicode.isprintable() and len(self.char_name) < 16:
                        self.char_name += ev.unicode
                    elif ev.key == pygame.K_ESCAPE:
                        self.state = state_CharManage

                elif self.state == state_LoadSelect:
                    if ev.key == pygame.K_UP:
                        self.selected_load_index = (self.selected_load_index - 1) % len(self.load_files)
                    elif ev.key == pygame.K_DOWN:
                        self.selected_load_index = (self.selected_load_index + 1) % len(self.load_files)
                    elif ev.key == pygame.K_RETURN:
                        selected_name = self.load_files[self.selected_load_index]
                        self.load_character(selected_name)
                    elif ev.key == pygame.K_ESCAPE:
                        self.state = state_CharManage
                    elif ev.key == pygame.K_DELETE:
                        # Delete selected save and its meta file
                        if not self.load_files:
                            break
                        to_delete = self.load_files[self.selected_load_index]
                        json_path = os.path.join("saves", f"{to_delete}.json")
                        meta_path = os.path.join("saves", f"{to_delete}_meta.json")
                        try:
                            if os.path.exists(json_path):
                                os.remove(json_path)
                                print(f"Deleted save: {json_path}")
                            if os.path.exists(meta_path):
                                os.remove(meta_path)
                                print(f"Deleted meta: {meta_path}")
                        except Exception as e:
                            print(f"⚠️ Failed deleting save files for '{to_delete}': {e}")
                        # refresh list and clamp index
                        self.load_files = sorted(
                            list({f[:-5] for f in os.listdir("saves")
                                  if f.endswith(".json") and not f.endswith("_meta.json")})
                        )
                        if not self.load_files:
                            self.state = state_CharManage
                        else:
                            self.selected_load_index = max(0, min(self.selected_load_index, len(self.load_files)-1))
                    return

                # Hub interactions
                elif self.state == state_Hub and ev.key == pygame.K_e:
                    if self.player:
                        for obj in self.interactables:
                            if obj.get("rect") and obj["rect"].colliderect(self.player.rect):
                                t = obj.get("type")
                                if t == "dungeon":
                                    self.state = state_DungeonSelect
                                elif t == "shop":
                                    self.open_shop()
                                elif t == "healer":
                                    self.open_healer()
                                # stop after first match
                                break

                # Dungeon select
                elif self.state == state_DungeonSelect:
                    if ev.key == pygame.K_1:
                        self.difficulty = "easy"; self.enter_dungeon()
                    elif ev.key == pygame.K_2:
                        self.difficulty = "normal"; self.enter_dungeon()
                    elif ev.key == pygame.K_3:
                        self.difficulty = "hard"; self.enter_dungeon()
                    elif ev.key == pygame.K_4:
                        self.difficulty = "legendary"; self.enter_dungeon()

                # death = return to menu
                elif self.state == state_Dead and ev.key == pygame.K_RETURN:
                    self.state = state_Menu
                    self.all_sprites.empty()
                    self.floating_texts.empty()
                    self.player_projectiles.empty()
                    self.enemy_projectiles.empty()
                    self.enemies.empty()
                    self.player = None

                # spellbook toggle
                elif ev.key == pygame.K_b:
                    self.spellbook_open = not self.spellbook_open
                    print("DEBUG: Spellbook ->", self.spellbook_open)


                #Inventory
                elif ev.key == pygame.K_i:
                  self.inventory_open = not getattr(self, "inventory_open", False)    

                # ability assignment / cast (1-4)
                elif ev.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                    if not self.player:
                        continue

                    print(f"DEBUG: ability_objects -> {self.player.ability_objects}")

                    idx = {pygame.K_1: 0, pygame.K_2: 1, pygame.K_3: 2, pygame.K_4: 3}[ev.key]

                    # Assign ability when spellbook is open
                    if self.spellbook_open and getattr(self.player, "hovered_ability", None):
                        hovered = self.player.hovered_ability
                        print(f"DEBUG: Hovered ability type = {type(hovered)} -> {hovered}")

                        # Only accept real Ability instances
                        from abilities import Ability
                        if isinstance(hovered, Ability):
                            self.player.ability_objects[idx] = hovered
                            print(f"DEBUG: Assigned real Ability object '{hovered.name}' to slot {idx+1}")
                            self.floating_texts.add(
                                FloatingText(f"Assigned to slot {idx+1}",
                                            self.player.rect.centerx,
                                            self.player.rect.top - 20,
                                            (200, 200, 50))
                            )
                        else:
                            print("⚠️ Ignored non-Ability hovered entry (probably legacy dict or invalid).")
                        continue  # Don't cast when assigning

                    # Cast ability when spellbook is closed
                    ability = None
                    if hasattr(self.player, "ability_objects"):
                        ability = self.player.ability_objects[idx]

                    if ability is None:
                        print(f"DEBUG: No ability bound to slot {idx+1}")
                        self.floating_texts.add(
                            FloatingText("Empty slot",
                                        self.player.rect.centerx,
                                        self.player.rect.top - 20,
                                        (180, 180, 180))
                        )
                        continue

                    now = pygame.time.get_ticks() / 1000.0

                    # Cast ability
                    from abilities import Ability
                    if isinstance(ability, Ability):
                        print(f"DEBUG: {ability.name} -> cooldown={ability.cooldown}, mana={ability.mana_cost}, effect={ability.effect}")
                        can = ability.can_cast(now, self.player)
                        if not can:
                            if self.player.mana < ability.mana_cost:
                                print(f"Not enough mana for {ability.name}.")
                                self.floating_texts.add(
                                    FloatingText("Not enough mana",
                                                self.player.rect.centerx,
                                                self.player.rect.top - 20,
                                                (50, 100, 255))
                                )
                            else:
                                print(f"{ability.name} is on cooldown.")
                                self.floating_texts.add(
                                    FloatingText("On cooldown",
                                                self.player.rect.centerx,
                                                self.player.rect.top - 20,
                                                (255, 200, 50))
                                )
                        else:
                            success = ability.cast(self.player, self, now)
                            if success:
                                print(f"{self.player.name} used {ability.name}!")
                                self.floating_texts.add(
                                    FloatingText(ability.name,
                                                self.player.rect.centerx,
                                                self.player.rect.top - 20,
                                                (150, 200, 255))
                                )
                            else:
                                print(f"Failed to cast {ability.name}")
                    else:
                        print(f"⚠️ Slot {idx+1} holds a non-Ability object; ignoring cast.")


            # mouse events (basic attack)
            elif ev.type == pygame.MOUSEBUTTONDOWN:
                if self.state == state_Dungeon:
                    if ev.button == 1 and self.player and getattr(self.player, "ranged", False):
                        if self.player.can_attack():
                            mx, my = pygame.mouse.get_pos()
                            world_x = mx + (self.camera.offset_x if self.camera else 0)
                            world_y = my + (self.camera.offset_y if self.camera else 0)
                            proj = PlayerProjectile(self.player, world_x, world_y, self.player.damage)
                            self.player_projectiles.add(proj)
                            self.all_sprites.add(proj)
                            self.player.record_attack()
                            self.sounds.play("attack")

                elif ev.type == pygame.MOUSEBUTTONDOWN and getattr(self, "inventory_open", False):
                    mx, my = ev.pos

                    # Inventory clicks
                    inv_x, inv_y = 60, 80
                    for row in range(INV_ROWS):
                        for col in range(INV_COLS):
                            idx = row * INV_COLS + col
                            rect = pygame.Rect(inv_x + col * (SLOT_SIZE + INV_MARGIN),
                                            inv_y + row * (SLOT_SIZE + INV_MARGIN),
                                            SLOT_SIZE, SLOT_SIZE)
                            if rect.collidepoint(mx, my):
                                if idx < len(self.player.inventory):
                                    item = self.player.inventory[idx]
                                    self.player.equip_item(item)
                                    # remove after equipping (equip_item doesn’t handle inventory removal)
                                    self.player.inventory.pop(idx)
                                    self.sounds.play("equip")
                                break

                    # Equipment clicks (unequip)
                    equip_x = inv_x + INV_COLS * (SLOT_SIZE + INV_MARGIN) + 100
                    equip_y = inv_y
                    for i, slot in enumerate(EQUIP_SLOTS_UI):
                        rect = pygame.Rect(equip_x, equip_y + i * 80, SLOT_SIZE, SLOT_SIZE)
                        if rect.collidepoint(mx, my):
                            unequipped = self.player.unequip_item(slot)
                            if unequipped:
                                self.player.inventory.append(unequipped)
                            break
                
    def save_character(self):
        if not self.player:
            return

        def serialize_item(item):
            """Return a JSON-serializable dict for an item instance or dict/None."""
            if item is None:
                return None
            # already a dict (old saves)
            if isinstance(item, dict):
                return item
            # try common converter methods
            for meth in ("to_dict", "as_dict", "toJSON", "to_json"):
                if hasattr(item, meth) and callable(getattr(item, meth)):
                    try:
                        return getattr(item, meth)()
                    except Exception as e:
                        print(f"⚠️ Error serializing item via {meth}: {e}")
                        return None
            # fallback: try to build a minimal dict from common attributes
            try:
                return {
                    "name": getattr(item, "name", getattr(item, "type", "Unknown")),
                    "slot": getattr(item, "slot", None),
                    "rarity": getattr(item, "rarity", None),
                    "armor": getattr(item, "armor", None),
                    "enchantments": getattr(item, "enchantments", []),
                }
            except Exception as e:
                # ultimate fallback: repr so JSON writer still has something
                print(f"⚠️ Failed fallback-serializing item: {e}")
                return {"__repr__": repr(item)}

        try:
            inv_serialized = [serialize_item(it) for it in getattr(self.player, "inventory", [])]
        except Exception as e:
            print(f"⚠️ Failed serializing inventory: {e}")
            inv_serialized = []

        try:
            # prefer live equipment map (Player.equip_item/unequip_item updates it) and fall back to equipped
            equipped_map = getattr(self.player, "equipment", None) or getattr(self.player, "equipped", {}) or {}
            equipped_serialized = {slot: serialize_item(item) for slot, item in equipped_map.items()}
        except Exception as e:
            print(f"⚠️ Failed serializing equipped items: {e}")
            equipped_serialized = {}

        data = {
            "name": getattr(self.player, "name", "Unnamed"),
            "cls": getattr(self.player, "class_name", getattr(self.player, "cls", None)),
            "inventory": inv_serialized,
            "equipped": equipped_serialized,
            # keep gold so player's money is saved/loaded
            "gold": int(getattr(self.player, "gold", 0)),
        }

        os.makedirs("saves", exist_ok=True)
        path = os.path.join("saves", f"{self.player.name}.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            print(f"💾 Saved character: {path}")
        except Exception as e:
            print(f"⚠️ Failed saving character file: {e}")


    def save_game(self):
        """Compatibility wrapper invoked from the Pause menu.
        Reuses save_character and writes minimal session metadata."""
        if not self.player:
            print("⚠️ No player to save.")
            return

        # Save character (inventory / equipped)
        try:
            self.save_character()
        except Exception as e:
            print(f"⚠️ Failed saving character: {e}")

        # Save lightweight session metadata for later use
        meta = {
            "player": self.player.name,
            "state": self.state,
            "difficulty": self.difficulty,
            "class": getattr(self.player, "class_name", None),
        }
        meta_path = os.path.join("saves", f"{self.player.name}_meta.json")
        try:
            with open(meta_path, "w") as f:
                json.dump(meta, f, indent=4)
            print(f"💾 Saved game meta: {meta_path}")
        except Exception as e:
            print(f"⚠️ Failed saving game meta: {e}")


    def load_character(self, name):
        path = os.path.join("saves", f"{name}.json")
        if not os.path.exists(path):
            print("⚠️ Save file not found:", path)
            return

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        cx, cy = self.screen.get_width() // 2, self.screen.get_height() // 2
        self.spawn_player(data.get("cls", self.class_list[0]), cx, cy, name=data.get("name"))

        # restore gold if present in save
        try:
            self.player.gold = int(data.get("gold", getattr(self.player, "gold", 0)))
        except Exception:
            try:
                if hasattr(self.player, "__dict__"):
                    self.player.__dict__["gold"] = int(data.get("gold", getattr(self.player, "gold", 0)))
            except Exception:
                pass

        # Robust item deserialization with slot normalization
        from items import Item as ItemClass, RARITY_COLORS

        # combined known slots for detection
        known_slots = []
        try:
            known_slots = list(EQUIP_SLOTS)
        except Exception:
            known_slots = list(EQUIP_SLOTS_UI)

        def normalize_slot(raw_slot):
            if raw_slot is None:
                return None
            if raw_slot in known_slots:
                return raw_slot
            rs = str(raw_slot).strip()
            # check if any known slot appears inside the string (case-insensitive)
            for s in known_slots:
                if s.lower() in rs.lower():
                    return s
            # fallback: last token (e.g. "Rare Chest" ->"Chest")
            parts = rs.split()
            if parts:
                last = parts[-1]
                for s in known_slots:
                    if last.lower() == s.lower():
                        return s
            # unknown: return original string (equip will fail but preserve data)
            return raw_slot

        def deserialize_item(d):
            if d is None:
                return None
            # already an Item instance
            if isinstance(d, ItemClass):
                item = d
                # normalize slot if present
                try:
                    item.slot = normalize_slot(getattr(item, "slot", None))
                except Exception:
                    pass
                return item
            # prefer class factory if available
            if hasattr(ItemClass, "from_dict") and callable(getattr(ItemClass, "from_dict")):
                try:
                    item = ItemClass.from_dict(d)
                    try:
                        item.slot = normalize_slot(getattr(item, "slot", None))
                    except Exception:
                        pass
                    return item
                except Exception as e:
                    print(f"⚠️ Item.from_dict failed: {e} — falling back for {d}")
            # if it's a dict, try to construct or create a lightweight fallback
            if isinstance(d, dict):
                # try positional constructor
                try:
                    item = ItemClass(d.get("name"), d.get("slot"), d.get("rarity"), d.get("armor", 0), d.get("enchantments", []))
                    item.slot = normalize_slot(getattr(item, "slot", None))
                    return item
                except Exception:
                    try:
                        item = ItemClass(**d)
                        item.slot = normalize_slot(getattr(item, "slot", None))
                        return item
                    except Exception:
                        # lightweight fallback
                        class SimpleItem:
                            def __init__(self, data):
                                self.name = data.get("name", "Unknown")
                                self.slot = normalize_slot(data.get("slot", None))
                                self.rarity = data.get("rarity", "common")
                                self.armor = data.get("armor", 0)
                                self.enchantments = data.get("enchantments", [])
                                self.color = RARITY_COLORS.get(self.rarity, (200,200,200))
                            def to_dict(self):
                                return {
                                    "name": self.name,
                                    "slot": self.slot,
                                    "rarity": self.rarity,
                                    "armor": self.armor,
                                    "enchantments": self.enchantments
                                }
                        return SimpleItem(d)
            # non-dict values -> wrap as simple item
            class SimpleItem2:
                def __init__(self, name):
                    self.name = name
                    self.slot = None
                    self.rarity = "common"
                    self.armor = 0
                    self.enchantments = []
                    self.color = RARITY_COLORS.get(self.rarity, (200,200,200))
                def to_dict(self):
                    return {"name": self.name}
            return SimpleItem2(str(d))

        try:
            self.player.inventory = [deserialize_item(d) for d in data.get("inventory", [])]
        except Exception as e:
            print(f"⚠️ Failed to load inventory -> {e}")
            self.player.inventory = []

        try:
            equipped_raw = data.get("equipped", {}) or {}
            equipped = {}
            for slot, val in equipped_raw.items():
                equipped_key = normalize_slot(slot)
                equipped[equipped_key] = deserialize_item(val)
            # ensure all expected slots exist
            try:
                for s in known_slots:
                    if s not in equipped:
                        equipped[s] = None
            except Exception:
                for s in EQUIP_SLOTS_UI:
                    if s not in equipped:
                        equipped[s] = None
            self.player.equipped = equipped
            self.player.equipment = equipped.copy()
            try:
                self.player.equipped = self.player.equipment.copy()
            except Exception:
                pass
            # Recalculate derived stats from equipped gear (important after load)
            try:
                self.player.recalculate_stats()
            except Exception as e:
                print(f"⚠️ Failed recalculating stats after load: {e}")
        except Exception as e:
            print(f"⚠️ Failed to load equipped items -> {e}")
            self.player.equipped = {s: None for s in known_slots}
            self.player.equipment = self.player.equipped.copy()

        self.state = state_Hub
        print(f"✅ Loaded character: {self.player.name}")


    # Update
    def update(self):
        if not self.player:
            return

        if self.door_cooldown > 0:
            self.door_cooldown -= 1

        keys = pygame.key.get_pressed()
        spd = getattr(self.player, "speed", 4)
        dx = dy = 0
        if keys[self.controls_p1["up"]]: dy = -spd
        if keys[self.controls_p1["down"]]: dy = spd
        if keys[self.controls_p1["left"]]: dx = -spd
        if keys[self.controls_p1["right"]]: dx = spd
        dt = self.clock.get_time() / 1000.0  # convert milliseconds to seconds
        self.player.update_regeneration(dt)
        if self.state in [state_Hub, state_Dungeon]:
            candidate = self.player.rect.move(dx, dy)
            if self.state == state_Hub:
                obstacles = [w.rect for w in self.walls]
                doors = []
            else:
                rx, ry = self.current_room
                obstacles = self.room_walls.get((rx, ry), [])
                doors = self.room_doors.get((rx, ry), [])

            blocked = False
            for obj in obstacles:
                if candidate.colliderect(obj):
                    if not any(candidate.colliderect(d.rect) for d in doors):
                        blocked = True
                        break

            if not blocked:
                self.player.update(dx, dy)
            else:
                self.player.update(0, 0)

            # door transitions
            if self.state == state_Dungeon:
                for door in doors:
                    if self.player.rect.colliderect(door.rect) and self.door_cooldown <= 0:
                        if door.leads_to == "EXIT":
                            if keys[pygame.K_e]:
                                sw, sh = self.screen.get_size()
                                self.player.rect.center = (sw//2, sh//2)
                                self.state = state_Hub
                        else:
                            prev_room = self.current_room
                            dest_room = door.leads_to
                            self.current_room = dest_room
                            self.place_player_at_door(from_door=door, dest_room=dest_room, prev_room=prev_room)
                            self.door_cooldown = 10
                        break

            # dungeon logic (enemies)
            if self.state == state_Dungeon and self.current_room is not None:
                enemies = self.room_enemies.get(self.current_room, [])
                for enemy in list(enemies):
                    dx_e = dy_e = 0
                    if self.player:
                        dx_rel = self.player.rect.centerx - enemy.rect.centerx
                        dy_rel = self.player.rect.centery - enemy.rect.centery
                        dist = math.hypot(dx_rel, dy_rel)
                        aggro_range = 600

                        if dist <= aggro_range:
                            if enemy.ranged:
                                if dist <= enemy.range:
                                    # Stop moving when in range to attack
                                    dx_e = dy_e = 0
                                else:
                                    # Move toward player if too far
                                    dx_e = (dx_rel / dist) * enemy.speed
                                    dy_e = (dy_rel / dist) * enemy.speed
                            else:
                                # Melee enemies always move toward player
                                if dist > 0:
                                    dx_e = (dx_rel / dist) * enemy.speed
                                    dy_e = (dy_rel / dist) * enemy.speed

                    enemy.move_and_animate(dx_e, dy_e, self.walls, player=self.player)

                    if self.player:
                        dx_rel = self.player.rect.centerx - enemy.rect.centerx
                        dy_rel = self.player.rect.centery - enemy.rect.centery
                        dist = math.hypot(dx_rel, dy_rel)
                        if dist <= 600:
                            # Debug: log attempt to attack
                            try:
                                print(f"[ENEMY ATTEMPT] {enemy.type} dist={dist:.1f} range={enemy.range} ranged={enemy.ranged} attack_speed={enemy.attack_speed}")
                            except Exception:
                                print(f"[ENEMY ATTEMPT] {getattr(enemy,'type','?')} dist={dist:.1f}")

                            damage_dealt = enemy.attack(self.player, projectile_group=self.enemy_projectiles, floating_group=self.floating_texts)

                            try:
                                print(f"[ENEMY ATTACK RESULT] {enemy.type} damage_dealt={damage_dealt}")
                            except Exception:
                                print(f"[ENEMY ATTACK RESULT] damage_dealt={damage_dealt}")

                            if damage_dealt > 0:
                                fx, fy = self.player.rect.centerx, self.player.rect.top - 20
                                self.floating_texts.add(FloatingText(f"-{damage_dealt}", fx, fy, color=(200,0,0)))

                    # player melee
                    if keys[pygame.K_SPACE] and not self.player.ranged and self.player.can_attack():
                        if self.player.rect.colliderect(enemy.rect):
                            dmg = self.player.attack(enemy)
                            if dmg > 0:
                                fx, fy = enemy.rect.centerx, enemy.rect.top - 20
                                self.floating_texts.add(FloatingText(f"-{dmg}", fx, fy, color=(255,50,50)))
                            break

                    # death cleanup
                    if enemy.hp <= 0:
                        if enemy in self.all_sprites:
                            self.all_sprites.remove(enemy)
                        if enemy in self.enemies:
                            self.enemies.remove(enemy)
                        if enemy in self.room_enemies.get(self.current_room, []):
                            self.room_enemies[self.current_room].remove(enemy)
                        self.sounds.play("death")
                        from items import drop_loot
                        drop_loot(enemy, self)  # pass enemy and game instance


                if self.player and self.player.hp <= 0:
                    self.state = state_Dead

                # projectiles update
                for proj in list(self.enemy_projectiles):
                    proj.update()
                    if hasattr(self, 'camera'):
                        screen_pos = self.camera.apply(proj.rect)
                        # Check if projectile is way off screen (with some margin)
                        margin = 100
                        if (screen_pos.right < -margin or 
                            screen_pos.left > self.screen.get_width() + margin or
                            screen_pos.bottom < -margin or 
                            screen_pos.top > self.screen.get_height() + margin):
                            proj.kill()
                
                for proj in list(self.player_projectiles):
                    proj.update()

                # Player projectiles vs enemies
                for proj in list(self.player_projectiles):
                    hit_list = [e for e in enemies if proj.rect.colliderect(e.rect)]
                    for e in hit_list:
                        dmg = proj.damage
                        e.take_damage(dmg, sprite_group=self.floating_texts)
                        self.floating_texts.add(FloatingText(f"-{dmg}", e.rect.centerx, e.rect.top - 20, color=(255, 200, 50)))
                        proj.kill()

                # Enemy projectiles vs player
                if self.player:
                    for proj in list(self.enemy_projectiles):
                        if proj.rect.colliderect(self.player.rect):
                            dmg = max(0, proj.damage - getattr(self.player, "armor", 0))
                            self.player.take_damage(dmg, self.floating_texts)
                            proj.kill()

                        # Trigger ability-specific on-hit effects
                        if hasattr(proj, "on_hit") and callable(proj.on_hit):
                            try:
                                proj.on_hit(e)  
                            except Exception as err:
                                print(f"⚠️ Error applying on-hit effect: {err}")

                        proj.kill()
                        break  # stop after first enemy hit


        # hub camera or dungeon camera update
        if self.state == state_Hub:
            sw, sh = self.screen.get_size()
            self.hub_cam_x = self.player.rect.centerx - sw//2
            self.hub_cam_y = self.player.rect.centery - sh//2
        elif self.state == state_Dungeon and self.camera:
            rx, ry = self.current_room
            room_px_w, room_px_h = self.room_sizes[(rx, ry)]
            room_origin_x = rx * room_px_w
            room_origin_y = ry * room_px_h
            self.camera.room_w = room_px_w
            self.camera.room_h = room_px_h
            self.camera.update(self.player.rect, room_origin_x, room_origin_y)

        # always update floating texts
        self.floating_texts.update()
        # Loot pickup
        for drop in pygame.sprite.spritecollide(self.player, self.loot_drops, False):
            drop.pickup(self.player)


    # Enter dungeon / build rooms
    def enter_dungeon(self):
        # Reset/clear prior dungeon state
        print("DEBUG: Entering dungeon:", self.difficulty)
        self.dungeon = Dungeon(self.difficulty)
        self.dungeon.generate()
        self.state = state_Dungeon
        # reset visited rooms for this dungeon run
        self.visited_rooms.clear()

        # clear sprite groups
        self.enemy_projectiles.empty()
        self.player_projectiles.empty()
        self.enemies.empty()
        self.room_enemies.clear()

        # clear room maps
        self.room_sizes.clear()
        self.room_walls.clear()
        self.room_doors.clear()
        self.room_floors.clear()
        self.room_horiz_walls_textures.clear()
        self.room_horiz_wall_map.clear()

        door_w, door_h = 120, 40

        # generate room sizes
        for ry in range(self.dungeon.grid_size):
            for rx in range(self.dungeon.grid_size):
                if self.dungeon.grid[ry][rx]:
                    w = random.randint(ROOM_W - 5, ROOM_W + 5) * TILE_SIZE
                    h = random.randint(ROOM_H - 5, ROOM_H + 5) * TILE_SIZE
                    self.room_sizes[(rx, ry)] = (w, h)

        # build rooms
        for (rx, ry), (room_px_w, room_px_h) in list(self.room_sizes.items()):
            room_origin_x = rx * room_px_w
            room_origin_y = ry * room_px_h
            cx = room_origin_x + room_px_w // 2
            cy = room_origin_y + room_px_h // 2

            # fill floor
            room_floor = []
            sheet = random.choice(self.floor_sheets) if self.floor_sheets else None
            frames = self.get_floor_frames(sheet, tile_size=TILE_SIZE, spacing=17) if sheet else []
            for y in range(0, room_px_h, TILE_SIZE):
                row = []
                for _ in range(0, room_px_w, TILE_SIZE):
                    row.append(random.choice(frames) if frames else pygame.Surface((TILE_SIZE, TILE_SIZE)))
                room_floor.append(row)
            self.room_floors[(rx, ry)] = room_floor

            # doors & walls
            doors = []
            walls = []

            # door sprites
            base_door_image = pygame.image.load(os.path.join(ASSET_DIR, "door.png")).convert_alpha()
            exit_door_image = pygame.image.load(os.path.join(ASSET_DIR, "door.png")).convert_alpha()

            # scaled to the correct size (80x90)
            base_door_image = pygame.transform.scale(base_door_image, (80, 90))
            exit_door_image = pygame.transform.scale(exit_door_image, (80, 90))

            # door and wall setup
            # north
            if ry > 0 and self.dungeon.grid[ry - 1][rx]:
                rect = pygame.Rect(cx - door_w // 2, room_origin_y, door_w, door_h)
                doors.append(Door(rect, (rx, ry - 1), sprite=base_door_image))
                if rect.left > room_origin_x:
                    walls.append(pygame.Rect(room_origin_x, room_origin_y, rect.left - room_origin_x, TILE_SIZE))
                if rect.right < room_origin_x + room_px_w:
                    walls.append(pygame.Rect(rect.right, room_origin_y, room_origin_x + room_px_w - rect.right, TILE_SIZE))
            else:
                walls.append(pygame.Rect(room_origin_x, room_origin_y, room_px_w, TILE_SIZE))

            # south door (flipped vertically)
            if ry < self.dungeon.grid_size - 1 and self.dungeon.grid[ry + 1][rx]:
                rect = pygame.Rect(cx - door_w // 2, room_origin_y + room_px_h - door_h, door_w, door_h)
                flipped_south = pygame.transform.flip(base_door_image, False, True)
                doors.append(Door(rect, (rx, ry + 1), sprite=flipped_south))
                if rect.left > room_origin_x:
                    walls.append(pygame.Rect(room_origin_x, room_origin_y + room_px_h - TILE_SIZE, rect.left - room_origin_x, TILE_SIZE))
                if rect.right < room_origin_x + room_px_w:
                    walls.append(pygame.Rect(rect.right, room_origin_y + room_px_h - TILE_SIZE, room_origin_x + room_px_w - rect.right, TILE_SIZE))
            else:
                walls.append(pygame.Rect(room_origin_x, room_origin_y + room_px_h - TILE_SIZE, room_px_w, TILE_SIZE))

            # west
            if rx > 0 and self.dungeon.grid[ry][rx - 1]:
                rect = pygame.Rect(room_origin_x, cy - door_w // 2, door_h, door_w)
                rotated = pygame.transform.rotate(base_door_image, 90)
                doors.append(Door(rect, (rx - 1, ry), sprite=rotated))
                if rect.top > room_origin_y:
                    walls.append(pygame.Rect(room_origin_x, room_origin_y, TILE_SIZE, rect.top - room_origin_y))
                if rect.bottom < room_origin_y + room_px_h:
                    walls.append(pygame.Rect(room_origin_x, rect.bottom, TILE_SIZE, room_origin_y + room_px_h - rect.bottom))
            else:
                walls.append(pygame.Rect(room_origin_x, room_origin_y, TILE_SIZE, room_px_h))

            # east
            if rx < self.dungeon.grid_size - 1 and self.dungeon.grid[ry][rx + 1]:
                rect = pygame.Rect(room_origin_x + room_px_w - door_h, cy - door_w // 2, door_h, door_w)
                rotated = pygame.transform.rotate(base_door_image, -90)
                doors.append(Door(rect, (rx + 1, ry), sprite=rotated))
                if rect.top > room_origin_y:
                    walls.append(pygame.Rect(room_origin_x + room_px_w - TILE_SIZE, room_origin_y, TILE_SIZE, rect.top - room_origin_y))
                if rect.bottom < room_origin_y + room_px_h:
                    walls.append(pygame.Rect(room_origin_x + room_px_w - TILE_SIZE, rect.bottom, TILE_SIZE, room_origin_y + room_px_h - rect.bottom))
            else:
                walls.append(pygame.Rect(room_origin_x + room_px_w - TILE_SIZE, room_origin_y, TILE_SIZE, room_px_h))

            # exit door 
            if (rx, ry) == self.dungeon.exit:
                exit_rect = pygame.Rect(cx - 60, cy - 30, 120, 60)
                doors.append(Door(exit_rect, "EXIT", sprite=exit_door_image))

            # Save results
            self.room_walls[(rx, ry)] = walls
            self.room_doors[(rx, ry)] = doors

            # horizontal wall textures pairing logic
            # choose pair (0+1) or (2+3)
            pair_choice_idx = random.choice([0, 1])  # 0 => (0,1) ; 1 => (2,3)
            if pair_choice_idx == 0:
                pair = (self.horiz_wall_sheets[0], self.horiz_wall_sheets[1])
            else:
                pair = (self.horiz_wall_sheets[2], self.horiz_wall_sheets[3])

            frames = []
            for s in pair:
                frames.extend(self.get_horizontal_wall_frames(s))
            if not frames:
                # fallback single dummy tile
                w = TILE_SIZE * 4
                h = TILE_SIZE * 2
                dummy = pygame.Surface((w, h), pygame.SRCALPHA)
                dummy.fill((120,120,120))
                frames = [dummy]

            # store the merged frames used for this room
            self.room_horiz_walls_textures[(rx, ry)] = frames
            self.room_horiz_wall_map[(rx, ry)] = []

            # assign textures to each horizontal wall rect
            for wall in walls:
                if wall.w > wall.h:  # horizontal
                    assigned = []
                    tile_w, tile_h = frames[0].get_size()
                    num_tiles = max(1, (wall.w + tile_w - 1) // tile_w)
                    for _ in range(num_tiles):
                        assigned.append(random.choice(frames))
                    # store a tuple of the wall rect and its assigned textures
                    self.room_horiz_wall_map[(rx, ry)].append((wall, assigned))

            # spawn enemies in this room
            self.spawn_enemies()

        # place player at dungeon entrance
        entrance_rx, entrance_ry = self.dungeon.entrance
        self.current_room = (entrance_rx, entrance_ry)
        # mark the entrance visited
        try:
            self.visited_rooms.add(self.current_room)
        except Exception:
            pass

        room_px_w, room_px_h = self.room_sizes[self.current_room]
        room_origin_x = entrance_rx * room_px_w
        room_origin_y = entrance_ry * room_px_h

        entrance_doors = self.room_doors.get(self.current_room, [])
        selected_door = None
        for door in entrance_doors:
            d = door.rect
            if d.top == room_origin_y or d.bottom == room_origin_y + room_px_h or d.left == room_origin_x or d.right == room_origin_x + room_px_w:
                selected_door = door
                break

        if selected_door:
            self.place_player_at_door(selected_door, self.current_room, prev_room=None)
        elif entrance_doors:
            self.place_player_at_door(entrance_doors[0], self.current_room, prev_room=None)
        else:
            if self.player:
                self.player.rect.center = (room_origin_x + room_px_w//2, room_origin_y + room_px_h//2)

        # init camera
        sw, sh = self.screen.get_size()
        self.camera = Camera(room_px_w, room_px_h, sw, sh)
        if self.player:
            self.camera.update(self.player.rect, room_origin_x, room_origin_y)

        print("DEBUG: Dungeon built; rooms:", len(self.room_sizes))
        self.play_music_for_difficulty()
    def play_music_for_difficulty(self):
        # Pick different music by difficulty
        tracks = {
            "easy": "assets/sounds/dungeon_easy.mp3",
            "normal": "assets/sounds/dungeon_normal.mp3",
            "hard": "assets/sounds/dungeon_hard.mp3",
            "legendary": "assets/sounds/dungeon_legendary.mp3",
        }

        difficulty = getattr(self, "difficulty", "normal").lower()
        track = tracks.get(difficulty, tracks["normal"])
        pygame.mixer.music.load(track)
        pygame.mixer.music.set_volume(0.4)
        pygame.mixer.music.play(-1)    
    
    
    # Floor / wall frame slicers
    def get_floor_frames(self, sheet, tile_size=32, spacing=17, margin_x=0, margin_y=1):
        # Slice floor sheet into tile_size x tile_size frames with spacing and margins
        frames = []
        if not sheet:
            return frames
        sw, sh = sheet.get_size()
        y = margin_y
        while y + tile_size <= sh:
            x = margin_x
            while x + tile_size <= sw:
                try:
                    r = int_rect_from(x, y, tile_size, tile_size)
                    frames.append(sheet.subsurface(r).copy())
                except Exception as e:
                    print(f"⚠️ floor subsurface failed at {(x,y)}: {e}")
                x += tile_size + spacing
            y += tile_size + spacing
        return frames

    def get_horizontal_wall_frames(self, sheet):
        # Slice horizontal wall sheet into 2 frames side by side
        frames = []
        if not sheet:
            return frames
        sw, sh = sheet.get_size()
        cols = 2
        # compute integer widths (divide remaining width evenly)
        frame_w = sw // cols
        frame_h = sh
        for i in range(cols):
            fx = i * frame_w
            try:
                r = int_rect_from(fx, 0, frame_w, frame_h)
                frames.append(sheet.subsurface(r).copy())
            except Exception as e:
                print(f"⚠️ horizontal subsurface failed for sheet at col {i}: {e}")
        # scale frames to tile proportions to match other assets
        scaled = []
        for f in frames:
            scaled.append(pygame.transform.scale(f, (TILE_SIZE * 4, TILE_SIZE * 2)))
        return scaled

    # Player utilities
    def place_player_at_door(self, from_door, dest_room=None, prev_room=None):
        if dest_room is None:
            dest_room = self.current_room
        offset = 64
        rx, ry = dest_room
        room_px_w, room_px_h = self.room_sizes[dest_room]
        room_origin_x = rx * room_px_w
        room_origin_y = ry * room_px_h

        # try to find matching door in dest_room if prev_room known
        matching_door = None
        if prev_room is not None:
            for d in self.room_doors.get(dest_room, []):
                if isinstance(d.leads_to, tuple) and d.leads_to == prev_room:
                    matching_door = d
                    break

        if matching_door is None:
            for d in self.room_doors.get(dest_room, []):
                r = d.rect
                if r.top == room_origin_y or r.bottom == room_origin_y + room_px_h or r.left == room_origin_x or r.right == room_origin_x + room_px_w:
                    matching_door = d
                    break

        if matching_door and self.player:
            r = matching_door.rect
            if r.top == room_origin_y:
                self.player.rect.midbottom = (r.centerx, r.bottom + offset)
            elif r.bottom == room_origin_y + room_px_h:
                self.player.rect.midtop = (r.centerx, r.top - offset)
            elif r.left == room_origin_x:
                self.player.rect.midright = (r.right + offset, r.centery)
            elif r.right == room_origin_x + room_px_w:
                self.player.rect.midleft = (r.left - offset, r.centery)
            else:
                self.player.rect.center = (room_origin_x + room_px_w//2, room_origin_y + room_px_h//2)
            # mark the destination room as visited
            try:
                if isinstance(dest_room, tuple):
                    self.visited_rooms.add(dest_room)
            except Exception:
                pass
        elif self.player:
            self.player.rect.center = (room_origin_x + room_px_w//2, room_origin_y + room_px_h//2)
            try:
                # when placed in the middle of a room, mark it visited
                if isinstance(dest_room, tuple):
                    self.visited_rooms.add(dest_room)
            except Exception:
                pass

    def spawn_enemies(self):
        print("[DEBUG] spawn_enemies(): starting")

        # Safety checks
        if not hasattr(self, "room_sizes") or not self.room_sizes:
            print("[DEBUG] spawn_enemies(): no rooms available (room_sizes empty)")
            return

        # clean old enemies safely
        if hasattr(self, "enemies"):
            for e in list(self.enemies):
                e.kill()
        self.enemies = pygame.sprite.Group()

        # keep only non-enemy sprites
        if hasattr(self, "all_sprites"):
            self.all_sprites = pygame.sprite.Group(
                [s for s in self.all_sprites if not getattr(s, "is_enemy", False)]
            )
        else:
            self.all_sprites = pygame.sprite.Group()

        self.room_enemies = {}

        # build lists of enemy types by category
        normal_names = [name for name, info in ENEMY_REGISTRY.items() if info.get("category") == "normal"]
        elite_names  = [name for name, info in ENEMY_REGISTRY.items() if info.get("category") == "elite"]
        boss_names   = [name for name, info in ENEMY_REGISTRY.items() if info.get("category") == "boss"]

        print(f"[DEBUG] registry counts -> normal: {len(normal_names)}, elite: {len(elite_names)}, boss: {len(boss_names)}")

        # room setup
        room_coords = list(self.room_sizes.keys())
        if not room_coords:
            print("[DEBUG] spawn_enemies(): no room coords found.")
            return

        boss_room = random.choice(room_coords) if boss_names else None
        total_spawned = 0

        for (rx, ry) in room_coords:
            w, h = self.room_sizes[(rx, ry)]
            room_x, room_y = rx * w, ry * h
            room_rect = pygame.Rect(room_x, room_y, w, h)
            self.room_enemies[(rx, ry)] = []

            # boss room
            if boss_room and (rx, ry) == boss_room:
                boss_type = random.choice(boss_names)
                bx = room_rect.centerx
                by = room_rect.centery
                boss = Enemy(boss_type, bx, by, difficulty=self.difficulty)
                boss.is_enemy = True
                self.enemies.add(boss)
                self.all_sprites.add(boss)
                self.room_enemies[(rx, ry)].append(boss)
                total_spawned += 1
                print(f"[DEBUG] Spawned BOSS '{boss_type}' at {(bx, by)} in room {(rx, ry)}")
                continue

            # normal enemies
            for _ in range(random.randint(2, 4)):
                if not normal_names:
                    break
                ex = random.randint(room_rect.left + 64, room_rect.right - 64)
                ey = random.randint(room_rect.top + 64, room_rect.bottom - 64)
                enemy_type = random.choice(normal_names)
                e = Enemy(enemy_type, ex, ey, difficulty=self.difficulty)
                e.is_enemy = True
                self.enemies.add(e)
                self.all_sprites.add(e)
                self.room_enemies[(rx, ry)].append(e)
                total_spawned += 1

            # elite enemies
            for _ in range(random.randint(0, 2)):
                if not elite_names:
                    break
                ex = random.randint(room_rect.left + 64, room_rect.right - 64)
                ey = random.randint(room_rect.top + 64, room_rect.bottom - 64)
                elite_type = random.choice(elite_names)
                el = Enemy(elite_type, ex, ey, difficulty=self.difficulty)
                el.is_enemy = True
                self.enemies.add(el)
                self.all_sprites.add(el)
                self.room_enemies[(rx, ry)].append(el)
                total_spawned += 1

        # debug summary
        print("\n--- ENEMY SPAWN DEBUG SUMMARY ---")
        print(f"Total in ENEMY_REGISTRY: {len(ENEMY_REGISTRY)}")
        print("Registry contents:", [f"{k}:{v['category']}" for k, v in ENEMY_REGISTRY.items()])
        print(f"Enemies in self.enemies group: {len(self.enemies)}")
        print(f"Enemies in self.all_sprites group: {len(self.all_sprites)}")
        print(f"Rooms with enemies: {len([r for r in self.room_enemies if self.room_enemies[r]])}")
        for coords, lst in self.room_enemies.items():
            if lst:
                print(f"  Room {coords} -> {len(lst)} enemies {[e.type for e in lst]}")
        print("----------------------------------\n")


    # Drawing
    def draw(self):
        self.screen.fill((0, 0, 0))
 
        # Shop & Healer screens
        if self.state == state_Shop:
            self.draw_shop(self.screen)
            pygame.display.flip()
            return
        if self.state == state_Healer:
            self.draw_healer(self.screen)
            pygame.display.flip()
            return
 
        if self.state == state_Menu:
            self.draw_menu()
 
        elif self.state == state_Settings:
            self.draw_settings()
 
        elif self.state == state_CharManage:
            self.draw_char_manage()
        elif self.state == state_CharCreate:
            self.draw_char_create()
        elif self.state == state_LoadSelect:
            self.draw_load_select()
 
 
        elif self.state == state_Hub:
            try:
                self.draw_simple_hub(self.screen)
            except Exception as e:
                print(f"⚠️ draw_simple_hub failed, falling back to draw_hub: {e}")
                self.draw_hub()
            self.draw_ui(self.screen)
            if self.spellbook_open:
                self.draw_spellbook(self.screen)
            pygame.mixer.music.fadeout(2000)  # fade out over 2 seconds    
 
        elif self.state == state_DungeonSelect:
            self.screen.fill((20, 20, 20))
            self.draw_text("Choose Dungeon Difficulty", (255, 255, 255), 200, 100)
            self.draw_text("1: Easy   2: Normal   3: Hard   4: Legendary", (200, 200, 50), 100, 200)
 
        elif self.state == state_Dungeon:
            self.draw_current_room()
            self.draw_ui(self.screen)
            if self.spellbook_open:
                self.draw_spellbook(self.screen)
 
        elif self.state == state_Dead:
            self.draw_text("You died. Press ENTER to return to Menu", (255, 255, 0), 120, 250)
            pygame.mixer.music.fadeout(2000)  # fade out over 2 seconds
 
        # Draw inventory overlay
        if getattr(self, "inventory_open", False):
            self.draw_inventory(self.screen)
 
        # Draw floating texts on top
        for text in self.floating_texts:
            draw_rect = self.camera.apply(text.rect) if self.state == state_Dungeon and self.camera else text.rect
            self.screen.blit(text.image, draw_rect.topleft)
 
        # Draw pause menu overlay if paused
        if self.state == state_Pause:
            self.draw_pause_menu()
 
        pygame.display.flip()
        
    def draw_char_manage(self):
        self.screen.fill((15, 15, 40))
        title_font = pygame.font.Font(None, 60)
        opt_font = pygame.font.Font(None, 40)

        title = title_font.render("Character Menu", True, (255, 255, 255))
        self.screen.blit(title, (self.screen.get_width()//2 - title.get_width()//2, 100))

        options = ["Create New Character", "Load Existing Character"]
        for i, opt in enumerate(options):
            color = (255, 255, 0) if i == self.selected_index else (200, 200, 200)
            text = opt_font.render(opt, True, color)
            self.screen.blit(text, (self.screen.get_width()//2 - text.get_width()//2, 250 + i * 60))


    def draw_char_create(self):
        self.screen.fill((20, 20, 50))
        title_font = pygame.font.Font(None, 60)
        opt_font = pygame.font.Font(None, 40)

        title = title_font.render("Create Character", True, (255, 255, 255))
        self.screen.blit(title, (self.screen.get_width()//2 - title.get_width()//2, 80))

        for i, cls in enumerate(self.class_list):
            color = (255, 255, 0) if i == self.selected_class_index else (200, 200, 200)
            text = opt_font.render(cls, True, color)
            self.screen.blit(text, (self.screen.get_width()//2 - text.get_width()//2, 200 + i * 50))

        name_text = opt_font.render(f"Name: {self.char_name}", True, (180, 180, 255))
        self.screen.blit(name_text, (self.screen.get_width()//2 - name_text.get_width()//2, 450))


    def draw_load_select(self):
        self.screen.fill((10, 10, 40))
        title_font = pygame.font.Font(None, 60)
        opt_font = pygame.font.Font(None, 40)
 
        title = title_font.render("Load Character", True, (255, 255, 255))
        self.screen.blit(title, (self.screen.get_width()//2 - title.get_width()//2, 100))
 
        for i, name in enumerate(self.load_files):
            color = (255, 255, 0) if i == self.selected_load_index else (200, 200, 200)
            text = opt_font.render(name, True, color)
            self.screen.blit(text, (self.screen.get_width()//2 - text.get_width()//2, 250 + i * 50))
        hint_font = pygame.font.Font(None, 20)
        hint = hint_font.render("Press DEL to delete selected save", True, (180,180,180))
        self.screen.blit(hint, (self.screen.get_width()//2 - hint.get_width()//2, self.screen.get_height() - 60))


    def draw_pause_menu(self):
         overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
         overlay.fill((0, 0, 0, 180))
         self.screen.blit(overlay, (0, 0))

         title_font = pygame.font.Font(None, 60)
         option_font = pygame.font.Font(None, 40)

         title = title_font.render("Paused", True, (255, 255, 255))
         self.screen.blit(title, (self.screen.get_width() // 2 - title.get_width() // 2, 150))

         for i, option in enumerate(self.pause_options):
             color = (255, 255, 0) if i == self.selected_pause_index else (200, 200, 200)
             text = option_font.render(option, True, color)
             self.screen.blit(text, (self.screen.get_width() // 2 - text.get_width() // 2, 280 + i * 60))


    def draw_menu(self):
        self.screen.fill((10, 10, 40))
        title_font = pygame.font.Font(None, 72)
        option_font = pygame.font.Font(None, 48)

        title = title_font.render("Dungeon Quest", True, (255, 255, 255))
        self.screen.blit(title, (self.screen.get_width()//2 - title.get_width()//2, 100))

        for i, option in enumerate(self.menu_options):
            color = (255, 255, 0) if i == self.selected_menu_index else (200, 200, 200)
            text = option_font.render(option, True, color)
           
            self.screen.blit(text, (self.screen.get_width()//2 - text.get_width()//2, 250 + i * 60))

    def draw_settings(self):
        self.screen.fill((20, 20, 50))
        title_font = pygame.font.Font(None, 60)
        option_font = pygame.font.Font(None, 40)

        # Draw title
        title = title_font.render("Settings", True, (255, 255, 255))
        self.screen.blit(title, (self.screen.get_width() // 2 - title.get_width() // 2, 100))

        # Loop through all settings options
        for i, option in enumerate(self.settings_options):
            color = (255, 255, 0) if i == self.selected_settings_index else (200, 200, 200)
            text_str = ""

            if option == "Resolution":
                res = self.available_resolutions[self.current_resolution_index]
                text_str = f"Resolution: {res[0]}x{res[1]}"
            elif option == "Fullscreen":
                text_str = f"Fullscreen: {'On' if self.fullscreen else 'Off'}"
            elif option == "Music Volume":
                text_str = f"Music Volume: {int(self.music_volume * 100)}%"
            elif option == "SFX Volume":
                text_str = f"SFX Volume: {int(self.sfx_volume * 100)}%"

            text = option_font.render(text_str, True, color)
            self.screen.blit(text, (self.screen.get_width() // 2 - text.get_width() // 2, 250 + i * 60))


    def draw_hub(self):
        sw, sh = self.screen.get_size()
        self.screen.fill((80,80,80))
        for w in self.walls:
            self.screen.blit(w.image, (w.rect.x - self.hub_cam_x, w.rect.y - self.hub_cam_y))
        for obj in self.interactables:
            r = obj["rect"]
            draw_rect = pygame.Rect(r.x - self.hub_cam_x, r.y - self.hub_cam_y, r.w, r.h)
       
        room_px_w, room_px_h = self.room_sizes[(rx, ry)]
        room_origin_x = rx * room_px_w
        room_origin_y = ry * room_px_h

        # draw floor tiles
        floor_map = self.room_floors.get((rx, ry))
        if floor_map:
            for ty, row in enumerate(floor_map):
                for tx, frame in enumerate(row):
                    sx = room_origin_x + tx * TILE_SIZE - self.camera.offset_x
                    sy = room_origin_y + ty * TILE_SIZE - self.camera.offset_y
                    if frame:
                        self.screen.blit(frame, (sx, sy))
        else:
            for y in range(0, room_px_h, TILE_SIZE):
                for x in range(0, room_px_w, TILE_SIZE):
                    sx = room_origin_x + x - self.camera.offset_x
                    sy = room_origin_y + y - self.camera.offset_y
                    pygame.draw.rect(self.screen, (100,100,100), (sx, sy, TILE_SIZE, TILE_SIZE))

        # draw vertical walls 
        vertical_tex = self.wall_textures.get("vertical")
        tw, th = vertical_tex.get_size()
        for w in self.room_walls.get((rx, ry), []):
            if w.h > w.w:  # vertical
                r = pygame.Rect(w.x - self.camera.offset_x, w.y - self.camera.offset_y, w.w, w.h)
                # tile vertical texture down the wall
                y = r.y
                y_end = r.y + r.h
                while y + th <= y_end:
                    self.screen.blit(vertical_tex, (r.x, y))
                    y += th
                if y < y_end:
                    clip = pygame.Rect(0, 0, tw, y_end - y)
                    self.screen.blit(vertical_tex, (r.x, y), clip)

        # draw horizontal walls using precomputed maps (clipped to wall extents)
        for wall, tex_list in self.room_horiz_wall_map.get((rx, ry), []):
            r = pygame.Rect(wall.x - self.camera.offset_x, wall.y - self.camera.offset_y, wall.w, wall.h)
            x = r.x
            x_end = r.x + r.w
            for tex in tex_list:
                tex_w = tex.get_width()
                # full tile fits
                if x + tex_w <= x_end:
                    self.screen.blit(tex, (x, r.y))
                else:
                    # partial clip on right edge
                    remaining = x_end - x
                    if remaining > 0:
                        clip_rect = pygame.Rect(0, 0, remaining, tex.get_height())
                        self.screen.blit(tex, (x, r.y), clip_rect)
                    break
                x += tex_w

        # draw corner connectors
        if self.corner_tex:
            cw, ch = self.corner_tex.get_size()
            for vwall in self.room_walls.get((rx, ry), []):
                if vwall.h > vwall.w:
                    vx1, vy1 = vwall.x, vwall.y
                    vx2, vy2 = vwall.x, vwall.y + vwall.h
                    for hwall in self.room_walls.get((rx, ry), []):
                        if hwall.w > hwall.h:
                            hx1, hy1 = hwall.x, hwall.y
                            hx2, hy2 = hwall.x + hwall.w, hwall.y
                            # top corner 
                            if abs(vx1 - hx1) < TILE_SIZE and abs(vy1 - hy2) < TILE_SIZE:
                                sx = vx1 - self.camera.offset_x
                                sy = vy1 - self.camera.offset_y
                                self.screen.blit(self.corner_tex, (sx, sy))
                            # bottom corner 
                            if abs(vx1 - hx2) < TILE_SIZE and abs(vy2 - hy1) < TILE_SIZE:
                                sx = vx1 - self.camera.offset_x
                                sy = vy2 - self.camera.offset_y - ch
                                self.screen.blit(self.corner_tex, (sx, sy))

        # draw doors
        for door in self.room_doors.get((rx, ry), []):
            door.draw(self.screen, (self.camera.offset_x, self.camera.offset_y))

            # Exit door
            if door.leads_to == "EXIT" and self.player.rect.colliderect(door.rect.inflate(20,20)):
                r = door.rect.move(-self.camera.offset_x, -self.camera.offset_y)
                self.draw_text("Press E to Exit", (255,255,0), r.x - 10, r.y - 30)

        # draw sprites (enemies & player & projectiles)
        for sprite in self.all_sprites:
            if not hasattr(sprite, "image") or sprite.image is None:
                # debug: detect empty/missing sprites
                print(f"🟥 Empty sprite found in all_sprites: {sprite}")
                continue
            draw_rect = self.camera.apply(sprite.rect)
            self.screen.blit(sprite.image, draw_rect.topleft)

        for proj in self.enemy_projectiles:
            draw_rect = self.camera.apply(proj.rect)
            self.screen.blit(proj.image, draw_rect.topleft)
        for proj in self.player_projectiles:
            draw_rect = self.camera.apply(proj.rect)
            self.screen.blit(proj.image, draw_rect.topleft)

        # draw minimap overlay for current dungeon
        try:
            self.draw_minimap(self.screen)
        except Exception as e:
            print(f"⚠️ Failed drawing minimap: {e}")


    def draw_simple_hub(self, surface):

        sw, sh = surface.get_size()
        surface.fill((80, 80, 80))

        ox = getattr(self, "hub_cam_x", 0)
        oy = getattr(self, "hub_cam_y", 0)

        # draw walls
        for w in self.walls:
            try:
                if hasattr(w, "image") and w.image:
                    surface.blit(w.image, (w.rect.x - ox, w.rect.y - oy))
                else:
                    pygame.draw.rect(surface, (100, 60, 30), (w.rect.x - ox, w.rect.y - oy, w.rect.w, w.rect.h))
            except Exception:
                pass

        # draw interactables
        for obj in self.interactables:
            r = obj.get("rect")
            typ = obj.get("type", "")
            if not r:
                continue
            draw_x = r.x - ox
            draw_y = r.y - oy
            if typ == "shop":
                if getattr(self, "shop_img", None):
                    img = pygame.transform.scale(self.shop_img, (r.w, r.h))
                    surface.blit(img, (draw_x, draw_y))
                else:
                    pygame.draw.rect(surface, (100, 180, 220), (draw_x, draw_y, r.w, r.h))
            elif typ == "healer":
                if getattr(self, "healer_img", None):
                    img = pygame.transform.scale(self.healer_img, (r.w, r.h))
                    surface.blit(img, (draw_x, draw_y))
                else:
                    pygame.draw.rect(surface, (120, 220, 150), (draw_x, draw_y, r.w, r.h))
            elif typ == "dungeon":
                pygame.draw.rect(surface, (180, 140, 60), (draw_x, draw_y, r.w, r.h))
            # label
            try:
                font = pygame.font.SysFont("Arial", 16, bold=True)
                label = font.render(typ.capitalize(), True, (10, 10, 10))
                surface.blit(label, (draw_x + 6, draw_y + 6))
            except Exception:
                pass

        # draw player
        if self.player:
            try:
                px = self.player.rect.x - ox
                py = self.player.rect.y - oy
                if hasattr(self.player, "image") and self.player.image:
                    surface.blit(self.player.image, (px, py))
                else:
                    pygame.draw.rect(surface, (50, 150, 50), (px, py, 32, 48))
            except Exception:
                pass

        # interaction hint
        try:
            for obj in self.interactables:
                if obj.get("rect") and self.player and obj["rect"].colliderect(self.player.rect):
                    self.draw_text("Press E to interact", (255, 255, 0), 20, sh - 60)
                    break
        except Exception:
            pass

    # UI drawing helpers
    def draw_text(self, text, color, x, y):
        font = pygame.font.SysFont("Arial", 28)
        surf = font.render(text, True, color)
        self.screen.blit(surf, (x, y))

    def spawn_player(self, chosen_class, x=None, y=None, name=None):
        # Ensure valid spawn coordinates
        if x is None:
            x = self.screen.get_width() // 2
        if y is None:
            y = self.screen.get_height() // 2

        # Resolve player name safely (prefer provided non-empty name)
        player_name = "Hero"
        if isinstance(name, str) and name.strip():
            player_name = name.strip()

        # Store the chosen class on the Game object for later reference
        self.class_name = chosen_class

        # Create and register the player with a guaranteed name
        self.player = Player(1, player_name, chosen_class, x, y)

        # Ensure the Player instance has the class_name attribute
        try:
            self.player.class_name = chosen_class
        except Exception:
            if hasattr(self.player, "__dict__"):
                self.player.__dict__["class_name"] = chosen_class

        # Create ability objects for this class and attach them to the player
        ability_objs = create_class_abilities(self.class_name)
        self.ability_objects = ability_objs
        try:
            self.player.ability_objects = ability_objs
        except Exception:
            if hasattr(self.player, "__dict__"):
                self.player.__dict__["ability_objects"] = ability_objs

        # Ensure basic inventory / equipment structures exist to avoid AttributeError
        try:
            equip_slots = EQUIP_SLOTS
        except NameError:
            equip_slots = EQUIP_SLOTS_UI

        default_equipped = {slot: None for slot in equip_slots}

        if not hasattr(self.player, "inventory") or self.player.inventory is None:
            try:
                self.player.inventory = []
            except Exception:
                if hasattr(self.player, "__dict__"):
                    self.player.__dict__["inventory"] = []

        if not hasattr(self.player, "equipped") or self.player.equipped is None:
            try:
                self.player.equipped = default_equipped.copy()
            except Exception:
                if hasattr(self.player, "__dict__"):
                    self.player.__dict__["equipped"] = default_equipped.copy()

        if not hasattr(self.player, "equipment") or self.player.equipment is None:
            try:
                self.player.equipment = default_equipped.copy()
            except Exception:
                if hasattr(self.player, "__dict__"):
                    self.player.__dict__["equipment"] = default_equipped.copy()

        # Ensure spellbook exists
        if not hasattr(self.player, "spellbook") or self.player.spellbook is None:
            try:
                self.player.spellbook = list(ability_objs) if ability_objs else []
            except Exception:
                if hasattr(self.player, "__dict__"):
                    self.player.__dict__["spellbook"] = list(ability_objs) if ability_objs else []

        # Ensure hovered_ability exists
        if not hasattr(self.player, "hovered_ability"):
            try:
                self.player.hovered_ability = None
            except Exception:
                if hasattr(self.player, "__dict__"):
                    self.player.__dict__["hovered_ability"] = None

        # Ensure sprite groups exist before adding
        if not hasattr(self, "all_sprites") or self.all_sprites is None:
            self.all_sprites = pygame.sprite.Group()
        self.all_sprites.add(self.player)

        # Ensure player has gold and stat methods
        try:
            if not hasattr(self.player, "gold"):
                self.player.gold = 0
        except Exception:
            try:
                self.player.__dict__["gold"] = 0
            except Exception:
                pass

    def draw_ui(self, surface):
        if not self.player:
            return
        # health bar
        bar_x, bar_y = 20, 20
        bar_w, bar_h = 200, 25
        pygame.draw.rect(surface, (50,50,50), (bar_x, bar_y, bar_w, bar_h))
        hp_ratio = max(0, self.player.hp / max(1, self.player.max_hp))
        pygame.draw.rect(surface, (200,50,50), (bar_x, bar_y, int(bar_w * hp_ratio), bar_h))
        pygame.draw.rect(surface, (0,0,0), (bar_x, bar_y, bar_w, bar_h), 2)
        font = pygame.font.SysFont("Arial", 20, bold=True)

        # round the displayed values
        hp_text = font.render(f"{int(self.player.hp)}/{int(self.player.max_hp)}", True, (255,255,255))
        surface.blit(hp_text, (bar_x + 60, bar_y))

        # mana bar
        mana_y = bar_y + bar_h + 10  # 10px below health bar
        pygame.draw.rect(surface, (50, 50, 50), (bar_x, mana_y, bar_w, bar_h))
        mana_ratio = max(0, self.player.mana / max(1, self.player.max_mana))
        pygame.draw.rect(surface, (50, 50, 200), (bar_x, mana_y, int(bar_w * mana_ratio), bar_h))
        pygame.draw.rect(surface, (0, 0, 0), (bar_x, mana_y, bar_w, bar_h), 2)

        # round the displayed values
        mana_text = font.render(f"{int(self.player.mana)}/{int(self.player.max_mana)}", True, (255, 255, 255))
        surface.blit(mana_text, (bar_x + 60, mana_y))
        
        # Gold display
        try:
            gold_text = font.render(f"Gold: {int(getattr(self.player, 'gold', 0))}", True, (255, 215, 0))
            surface.blit(gold_text, (surface.get_width() - gold_text.get_width() - 20, 20))
        except Exception:
            pass

        # ability bar
        sw, sh = surface.get_size()
        ab_w, ab_h = 300, 60
        ab_x = (sw - ab_w)//2
        ab_y = sh - ab_h - 20
        pygame.draw.rect(surface, (30,30,30), (ab_x, ab_y, ab_w, ab_h))
        pygame.draw.rect(surface, (0,0,0), (ab_x, ab_y, ab_w, ab_h), 3)

        slot_size, padding = 50, 10
        for i in range(4):
            sx = ab_x + 10 + i*(slot_size + padding)
            sy = ab_y + 5
            pygame.draw.rect(surface, (70,70,70), (sx, sy, slot_size, slot_size))

            border_color = (255,255,0) if i == self.selected_ability else (200,200,200)
            border_thickness = 4 if i == self.selected_ability else 2
            pygame.draw.rect(surface, border_color, (sx, sy, slot_size, slot_size), border_thickness)

            # draw ability icon
            ability = self.player.ability_objects[i] if hasattr(self.player, "ability_objects") else None
            if ability:
                try:
                    icon = pygame.image.load(f"assets/{ability.name}.png").convert_alpha()
                    icon = pygame.transform.scale(icon, (slot_size-10, slot_size-10))
                    surface.blit(icon, (sx+5, sy+5))

                    now = pygame.time.get_ticks() / 1000
                    remaining = max(0, ability.cooldown - (now - ability.last_used))
                    if remaining > 0:
                        overlay = pygame.Surface((slot_size-10, slot_size-10), pygame.SRCALPHA)
                        overlay.fill((0, 0, 0, 150))  # semi-transparent black
                        surface.blit(overlay, (sx+5, sy+5))

                        # cooldown text
                        cd_label = font.render(f"{int(remaining)+1}", True, (255, 255, 255))
                        surface.blit(cd_label, (sx + slot_size//3, sy + slot_size//3))
                except Exception as e:
                    print(f"DEBUG: Missing icon for {ability.name}: {e}")
                    pygame.draw.rect(surface, (100,150,250), (sx+5, sy+5, slot_size-10, slot_size-10))
            else:
                pygame.draw.rect(surface, (100,150,250), (sx+5, sy+5, slot_size-10, slot_size-10))

            label = font.render(str(i+1), True, (255,255,255))
            surface.blit(label, (sx + 5, sy + 2))


    def draw_spellbook(self, surface):
        if not self.player:
            return

        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, 0))

        font = pygame.font.SysFont("Arial", 28)
        title = font.render(f"{self.player.name}'s Spellbook (Press B to close)", True, (255, 255, 255))
        surface.blit(title, (50, 20))

        self.player.hovered_ability = None
        mx, my = pygame.mouse.get_pos()
        y_offset = 100

        # Spellbook entries  
        for i, ability in enumerate(self.player.spellbook):
            rect = pygame.Rect(80, y_offset + i * 60, 300, 50)
            pygame.draw.rect(surface, (70, 70, 120), rect)

            # Handle both Ability instances and old dicts
            if hasattr(ability, "icon") and ability.icon:
                icon = pygame.transform.scale(ability.icon, (40, 40))
                surface.blit(icon, (rect.x + 5, rect.y + 5))
                name = getattr(ability, "name", "Unknown")
            elif isinstance(ability, dict):
                if "icon" in ability and ability["icon"]:
                    icon = pygame.transform.scale(ability["icon"], (40, 40))
                    surface.blit(icon, (rect.x + 5, rect.y + 5))
                name = ability.get("name", "Unknown")
            else:
                name = getattr(ability, "name", "Unknown")

            text = font.render(name, True, (255, 255, 0))
            surface.blit(text, (rect.x + 50, rect.y + 10))

            # Hover selection
            if rect.collidepoint(mx, my):
                pygame.draw.rect(surface, (200, 200, 0), rect, 3)
                self.player.hovered_ability = ability

        # Instruction text
        instr_font = pygame.font.SysFont("Arial", 20)
        instr = instr_font.render("Hover over an ability and press 1–4 to assign it", True, (200, 200, 200))
        surface.blit(instr, (50, surface.get_height() - 80))

        # Quickbar display (slots 1–4)
        quickbar_y = surface.get_height() - 60
        quickbar_font = pygame.font.SysFont("Arial", 20, bold=True)

        for i in range(4):
            slot_x = 80 + i * 100
            pygame.draw.rect(surface, (60, 60, 60), (slot_x, quickbar_y, 90, 40))
            pygame.draw.rect(surface, (200, 200, 200), (slot_x, quickbar_y, 90, 40), 2)

            ability = self.player.ability_objects[i] if hasattr(self.player, "ability_objects") else None

            if hasattr(ability, "name"):
                label_text = ability.name
            elif isinstance(ability, dict):
                label_text = ability.get("name", "Unknown")
            else:
                label_text = "Empty"

            label = quickbar_font.render(f"{i+1}: {label_text}", True, (255, 255, 255))
            surface.blit(label, (slot_x + 10, quickbar_y + 10))


    def draw_inventory(self, surface):
        if not getattr(self, "inventory_open", False):
            return

        font = pygame.font.SysFont("Arial", 18)
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, 0))

        title = pygame.font.SysFont("Arial", 28, bold=True).render(
            "Inventory (Press I to close)", True, (255, 255, 255)
        )
        surface.blit(title, (50, 20))

        # Inventory grid
        inv_x, inv_y = 60, 80
        mx, my = pygame.mouse.get_pos()
        hovered_item = None

        for row in range(INV_ROWS):
            for col in range(INV_COLS):
                idx = row * INV_COLS + col
                rect = pygame.Rect(inv_x + col * (SLOT_SIZE + INV_MARGIN),
                                inv_y + row * (SLOT_SIZE + INV_MARGIN),
                                SLOT_SIZE, SLOT_SIZE)
                pygame.draw.rect(surface, (80, 80, 80), rect)
                pygame.draw.rect(surface, (30, 30, 30), rect, 2)

                if idx < len(self.player.inventory):
                    item = self.player.inventory[idx]
                    # Color border by rarity
                    pygame.draw.rect(surface, item.color, rect, 3)
                    # Render item name
                    text = font.render(item.slot[0], True, (255, 255, 255))
                    surface.blit(text, (rect.x + 22, rect.y + 20))
                    if rect.collidepoint(mx, my):
                        hovered_item = item

        #Equipment slots
        equip_x = inv_x + INV_COLS * (SLOT_SIZE + INV_MARGIN) + 100
        equip_y = inv_y
        equip_font = pygame.font.SysFont("Arial", 20, bold=True)
        for i, slot in enumerate(EQUIP_SLOTS_UI):
            rect = pygame.Rect(equip_x, equip_y + i * 80, SLOT_SIZE, SLOT_SIZE)
            pygame.draw.rect(surface, (100, 100, 100), rect)
            pygame.draw.rect(surface, (50, 50, 50), rect, 2)
            text = equip_font.render(slot, True, (255, 255, 255))
            surface.blit(text, (rect.x + SLOT_SIZE + 10, rect.y + 10))

            equipped = self.player.equipment.get(slot)
            if equipped:
                pygame.draw.rect(surface, equipped.color, rect, 3)
                surface.blit(font.render(slot[0], True, (255, 255, 255)),
                            (rect.x + 22, rect.y + 20))
                if rect.collidepoint(mx, my):
                    hovered_item = equipped

        # Tooltip 
        if hovered_item:
            self.draw_item_tooltip(surface, hovered_item, mx, my)


    def draw_item_tooltip(self, surface, item, x, y):
        font = pygame.font.SysFont("Arial", 18)
        lines = [f"{item.name} [{item.rarity}]",
                f"Armor: {item.armor}"]
        for ench in item.enchantments:
            value = ench.get("value", random.randint(ench["min"], ench["max"]))
            sign = "%" if ench["type"] == "percent" else ""
            lines.append(f"+{value}{sign} {ench['name']}")


        padding = 8
        width = max(font.size(line)[0] for line in lines) + padding * 2
        height = len(lines) * 22 + padding * 2

        tooltip = pygame.Surface((width, height))
        tooltip.fill((30, 30, 30))
        pygame.draw.rect(tooltip, item.color, tooltip.get_rect(), 2)

        for i, line in enumerate(lines):
            text = font.render(line, True, (255, 255, 255))
            tooltip.blit(text, (padding, padding + i * 22))

        surface.blit(tooltip, (x + 20, y))



    def draw_minimap(self, surface):
        if not getattr(self, "dungeon", None):
            return
        grid_size = getattr(self.dungeon, "grid_size", None)
        if not grid_size:
            return

        # dynamic cell size so the map fits a small corner
        max_pixels = 160
        cell = max(4, min(20, max_pixels // max(1, grid_size)))
        map_w = cell * grid_size
        map_h = cell * grid_size

        padding = 8
        margin = 12
        sx = surface.get_width() - map_w - margin
        sy = margin

        # background & border
        bg = pygame.Surface((map_w + padding, map_h + padding), pygame.SRCALPHA)
        bg.fill((10, 10, 10, 190))
        surface.blit(bg, (sx - padding//2, sy - padding//2))
        pygame.draw.rect(surface, (200, 200, 200), (sx - 2, sy - 2, map_w + 4, map_h + 4), 1)

        # visited rooms + current room
        reveal = set(getattr(self, "visited_rooms", set()))
        cur = getattr(self, "current_room", None)
        if isinstance(cur, tuple):
            reveal.add(cur)

        # draw only revealed cells
        for ry in range(grid_size):
            for rx in range(grid_size):
                if (rx, ry) not in reveal:
                    continue  # skip unvisited rooms entirely

                cell_x = sx + rx * cell
                cell_y = sy + ry * cell
                rect = pygame.Rect(cell_x, cell_y, cell - 1, cell - 1)

                # if the dungeon.grid says room doesn't exist but it's in reveal, treat as visited
                exists = True
                try:
                    exists = bool(self.dungeon.grid[ry][rx])
                except Exception:
                    exists = True

                if not exists:
                    color = (30, 30, 30)
                else:
                    if (rx, ry) == getattr(self, "current_room", None):
                        color = (50, 200, 200)  # current
                    else:
                        color = (80, 200, 80)   # visited

                pygame.draw.rect(surface, color, rect)

    def rarity_sell_value(self, rarity):
        mapping = {"Normal":1, "Magic":2, "Rare":4, "Epic":8, "Legendary":16,
                   "common":1, "Common":1}
        return mapping.get(rarity, 1)

    def rarity_buy_cost(self, rarity):
        return self.rarity_sell_value(rarity) * 2

    def make_random_item_for_rarity(self, rarity):
        from items import RARITY_COLORS
        try:
            slots = list(EQUIP_SLOTS) if 'EQUIP_SLOTS' in globals() else list(EQUIP_SLOTS_UI)
        except Exception:
            slots = list(EQUIP_SLOTS_UI)
        slot = random.choice(slots) if slots else "Chest"
        name = f"{rarity} {slot}"
        armor = {"Normal":1,"Magic":2,"Rare":4,"Epic":8,"Legendary":12}.get(rarity, 1) * random.randint(1,3)
        color = RARITY_COLORS.get(rarity, (200,200,200))
        class ShopItem:
            def __init__(self, name, slot, rarity, armor, color):
                self.name = name
                self.slot = slot
                self.rarity = rarity
                self.armor = armor
                self.enchantments = []
                self.color = color
            def to_dict(self):
                return {"name":self.name,"slot":self.slot,"rarity":self.rarity,"armor":self.armor,"enchantments":self.enchantments}
        return ShopItem(name, slot, rarity, armor, color)

    def open_shop(self):
        self.shop_selected_index = 0
        self.shop_mode = "sell"
        self.state = state_Shop

    def open_healer(self):
        self.healer_confirm = False
        self.state = state_Healer

    def sell_selected_item(self, idx):
        if not self.player:
            return
        inv = getattr(self.player, "inventory", [])
        if idx < 0 or idx >= len(inv):
            return
        # support both object instances and dict-serialized items
        try:
            item = self.player.inventory.pop(idx)
        except Exception:
            try:
                # best effort removal for odd inventory types
                item = inv[idx]
                del inv[idx]
            except Exception:
                return
        if isinstance(item, dict):
            rarity = item.get("rarity", item.get("type", "Normal"))
        else:
            rarity = getattr(item, "rarity", getattr(item, "rarity_type", "Normal"))
        gained = self.rarity_sell_value(rarity)
        try:
            self.player.gold += gained
        except Exception:
            try: self.player.__dict__["gold"] = getattr(self.player, "gold", 0) + gained
            except Exception: pass
        self.floating_texts.add(FloatingText(f"+{gained}g", self.player.rect.centerx, self.player.rect.top - 20, (255,215,0)))

    def buy_item_by_rarity(self, rarity):
        cost = self.rarity_buy_cost(rarity)
        if getattr(self.player, "gold", 0) < cost:
            self.floating_texts.add(FloatingText("Not enough gold", self.player.rect.centerx, self.player.rect.top - 20, (200,50,50)))
            return
        item = self.make_random_item_for_rarity(rarity)
        try:
            self.player.gold -= cost
        except Exception:
            try: self.player.__dict__["gold"] = getattr(self.player, "gold", 0) - cost
            except Exception: pass
        # add to inventory
        try:
            self.player.inventory.append(item)
        except Exception:
            if hasattr(self.player, "__dict__"):
                inv = self.player.__dict__.get("inventory", [])
                inv.append(item)
                self.player.__dict__["inventory"] = inv
        self.floating_texts.add(FloatingText(f"-{cost}g", self.player.rect.centerx, self.player.rect.top - 20, (255,215,0)))

    def draw_shop(self, surface):
        surface.fill((30, 24, 40))
        title = pygame.font.Font(None, 48).render("Shop", True, (255,255,255))
        surface.blit(title, (surface.get_width()//2 - title.get_width()//2, 40))
        font = pygame.font.SysFont("Arial", 20)
        surface.blit(font.render("Your Items (S to sell)", True, (200,200,200)), (60, 110))
        # build clickable sell buttons for each inventory item
        self._shop_item_rects = []
        inv = getattr(self.player, "inventory", [])
        for i, item in enumerate(inv):
            color = (255,255,0) if i == self.shop_selected_index else (200,200,200)
            name = getattr(item, "name", None) or (item.get("name") if isinstance(item, dict) else str(item))
            rarity = getattr(item, "rarity", None) or (item.get("rarity") if isinstance(item, dict) else "Normal")
            sell_price = self.rarity_sell_value(rarity)
            text = f"{name} [{rarity}] - Sell:{sell_price}g"
            surface.blit(font.render(text, True, color), (60, 140 + i*28))
            # sell button on the right of the row
            btn_w, btn_h = 68, 22
            bx = 60 + 420
            by = 140 + i*28
            btn_rect = pygame.Rect(bx, by, btn_w, btn_h)
            pygame.draw.rect(surface, (200,80,40), btn_rect)
            try:
                btn_txt = pygame.font.SysFont("Arial", 14).render("Sell", True, (255,255,255))
                surface.blit(btn_txt, (bx + (btn_w - btn_txt.get_width())//2, by + (btn_h - btn_txt.get_height())//2))
            except Exception:
                pass
            self._shop_item_rects.append((btn_rect, i))
         # buy options
        bx = surface.get_width() - 420
        surface.blit(font.render("Buy Random (1-5):", True, (200,200,200)), (bx, 110))
        rarities = ["Normal","Magic","Rare","Epic","Legendary"]
        for i, r in enumerate(rarities):
             cost = self.rarity_buy_cost(r)
             text = f"{i+1}. {r} - {cost}g"
             surface.blit(font.render(text, True, (220,220,220)), (bx, 140 + i*28))
         # Gold display and instructions
        surface.blit(font.render(f"Gold: {int(getattr(self.player,'gold',0))}", True, (255,215,0)), (60, surface.get_height() - 60))
        surface.blit(font.render("ESC to exit shop", True, (180,180,180)), (surface.get_width()//2 - 80, surface.get_height() - 60))

    def draw_healer(self, surface):
        surface.fill((20, 30, 20))
        title = pygame.font.Font(None, 48).render("Healer", True, (255,255,255))
        surface.blit(title, (surface.get_width()//2 - title.get_width()//2, 40))
        font = pygame.font.SysFont("Arial", 20)
        cost = 15
        surface.blit(font.render(f"Heal fully (HP+Mana) for {cost} gold", True, (220,220,220)), (surface.get_width()//2 - 180, 140))
        surface.blit(font.render(f"Gold: {int(getattr(self.player,'gold',0))}g", True, (255,215,0)), (surface.get_width()//2 - 60, 180))
        surface.blit(font.render("Press ENTER to confirm, ESC to cancel", True, (180,180,180)), (surface.get_width()//2 - 160, surface.get_height() - 80))

    def draw_current_room(self):
        """Render the currently active dungeon room (safe/fails quietly)."""
        if not getattr(self, "dungeon", None) or self.current_room is None:
            return

        try:
            rx, ry = self.current_room
            room_px_w, room_px_h = self.room_sizes.get((rx, ry), (0, 0))
            room_origin_x = rx * room_px_w
            room_origin_y = ry * room_px_h

            # camera offsets 
            offset_x = getattr(self.camera, "offset_x", 0) if getattr(self, "camera", None) else 0
            offset_y = getattr(self.camera, "offset_y", 0) if getattr(self, "camera", None) else 0

            # Draw enemy projectiles
            for proj in self.enemy_projectiles:
                screen_pos = self.camera.apply(proj.rect) if self.camera else proj.rect
                self.screen.blit(proj.image, screen_pos)

            # draw floor tiles
            floor_map = self.room_floors.get((rx, ry))
            if floor_map:
                for ty, row in enumerate(floor_map):
                    for tx, frame in enumerate(row):
                        sx = room_origin_x + tx * TILE_SIZE - offset_x
                        sy = room_origin_y + ty * TILE_SIZE - offset_y
                        if frame:
                            # Draw enemy projectiles
                            for proj in self.enemy_projectiles:
                                self.screen.blit(proj.image, (proj.rect.x - offset_x, proj.rect.y - offset_y))
                            try:
                                self.screen.blit(frame, (sx, sy))
                            except Exception:
                                # sometimes frames may be invalid surfaces
                                pygame.draw.rect(self.screen, (90,90,90), (sx, sy, TILE_SIZE, TILE_SIZE))
                        else:
                            pygame.draw.rect(self.screen, (90,90,90), (sx, sy, TILE_SIZE, TILE_SIZE))
            else:
                # fallback tiled grey floor
                for y in range(0, room_px_h or 1, TILE_SIZE):
                    for x in range(0, room_px_w or 1, TILE_SIZE):
                        sx = room_origin_x + x - offset_x
                        sy = room_origin_y + y - offset_y
                        pygame.draw.rect(self.screen, (100,100,100), (sx, sy, TILE_SIZE, TILE_SIZE))

            # vertical walls
            vertical_tex = self.wall_textures.get("vertical") if hasattr(self, "wall_textures") else None
            if vertical_tex:
                tw, th = vertical_tex.get_size()
            else:
                tw = th = TILE_SIZE
            for w in self.room_walls.get((rx, ry), []):
                if w.h > w.w:  # vertical wall
                    r = pygame.Rect(w.x - offset_x, w.y - offset_y, w.w, w.h)
                    # tile vertical texture down the wall
                    y = r.y
                    y_end = r.y + r.h
                    while y + th <= y_end:
                        try:
                            self.screen.blit(vertical_tex, (r.x, y))
                        except Exception:
                            pygame.draw.rect(self.screen, (120,80,40), (r.x, y, tw, th))
                        y += th
                    if y < y_end:
                        # partial tile
                        try:
                            clip = pygame.Rect(0, 0, tw, y_end - y)
                            self.screen.blit(vertical_tex, (r.x, y), clip)
                        except Exception:
                            pygame.draw.rect(self.screen, (120,80,40), (r.x, y, r.w, y_end - y))

            # horizontal walls using precomputed maps
            for wall, tex_list in self.room_horiz_wall_map.get((rx, ry), []):
                r = pygame.Rect(wall.x - offset_x, wall.y - offset_y, wall.w, wall.h)
                x = r.x
                x_end = r.x + r.w
                for tex in tex_list:
                    try:
                        tex_w = tex.get_width()
                    except Exception:
                        tex_w = TILE_SIZE * 4
                    if x + tex_w <= x_end:
                        try:
                            self.screen.blit(tex, (x, r.y))
                        except Exception:
                            pygame.draw.rect(self.screen, (110,110,110), (x, r.y, tex_w, r.h))
                    else:
                        remaining = x_end - x
                        if remaining > 0:
                            try:
                                clip_rect = pygame.Rect(0, 0, remaining, tex.get_height())
                                self.screen.blit(tex, (x, r.y), clip_rect)
                            except Exception:
                                pygame.draw.rect(self.screen, (110,110,110), (x, r.y, remaining, r.h))
                        break
                    x += tex_w

            # corner connectors (optional)
            if getattr(self, "corner_tex", None):
                cw, ch = self.corner_tex.get_size()
                for vwall in self.room_walls.get((rx, ry), []):
                    if vwall.h > vwall.w:
                        vx1, vy1 = vwall.x, vwall.y
                        vy2 = vwall.y + vwall.h
                        for hwall in self.room_walls.get((rx, ry), []):
                            if hwall.w > hwall.h:
                                hx1, hy1 = hwall.x, hwall.y
                                hx2 = hwall.x + hwall.w
                                hy2 = hwall.y
                                # top corner
                                if abs(vx1 - hx1) < TILE_SIZE and abs(vy1 - hy2) < TILE_SIZE:
                                    sx = vx1 - offset_x
                                    sy = vy1 - offset_y
                                    try: self.screen.blit(self.corner_tex, (sx, sy))
                                    except Exception: pass
                                # bottom corner
                                if abs(vx1 - hx2) < TILE_SIZE and abs(vy2 - hy1) < TILE_SIZE:
                                    sx = vx1 - offset_x
                                    sy = vy2 - offset_y - ch
                                    try: self.screen.blit(self.corner_tex, (sx, sy))
                                    except Exception: pass

            # doors
            for door in self.room_doors.get((rx, ry), []):
                try:
                    # Door.draw expects screen and (offset_x, offset_y) tuple
                    door.draw(self.screen, (offset_x, offset_y))
                except Exception:
                    # fallback: draw simple rect
                    try:
                        dr = door.rect
                        self.screen.fill((120,120,120), (dr.x - offset_x, dr.y - offset_y, dr.w, dr.h))
                    except Exception:
                        pass

                # Exit hint
                try:
                    if door.leads_to == "EXIT" and self.player and self.player.rect.colliderect(door.rect.inflate(20,20)):
                        r = door.rect.move(-offset_x, -offset_y)
                        self.draw_text("Press E to Exit", (255,255,0), r.x - 10, r.y - 30)
                except Exception:
                    pass

            # draw sprites
            for sprite in list(self.all_sprites):
                try:
                    img = getattr(sprite, "image", None)
                    if not img:
                        continue
                    if getattr(self, "camera", None) and hasattr(self.camera, "apply"):
                        draw_rect = self.camera.apply(sprite.rect)
                        self.screen.blit(img, draw_rect.topleft)
                    else:
                        self.screen.blit(img, (sprite.rect.x - offset_x, sprite.rect.y - offset_y))
                except Exception:
                    # skip broken sprites
                    continue

            # draw projectiles
            for proj in list(self.enemy_projectiles):
                try:
                    if getattr(self, "camera", None) and hasattr(self.camera, "apply"):
                        draw_rect = self.camera.apply(proj.rect)
                        self.screen.blit(proj.image, draw_rect.topleft)
                    else:
                        self.screen.blit(proj.image, (proj.rect.x - offset_x, proj.rect.y - offset_y))
                except Exception:
                    continue
            for proj in list(self.player_projectiles):
                try:
                    if getattr(self, "camera", None) and hasattr(self.camera, "apply"):
                        draw_rect = self.camera.apply(proj.rect)
                        self.screen.blit(proj.image, draw_rect.topleft)
                    else:
                        self.screen.blit(proj.image, (proj.rect.x - offset_x, proj.rect.y - offset_y))
                except Exception:
                    continue

            # minimap overlay
            try:
                self.draw_minimap(self.screen)
            except Exception:
                pass

        except Exception as e:
            # Fail silently but log for debug
            print(f"⚠️ draw_current_room failed: {e}")

