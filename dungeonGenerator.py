import random
import pygame

class Dungeon:
    def __init__(self, grid_size=15, difficulty="normal"):
        if isinstance(grid_size, str):
            difficulty = grid_size
            grid_size = 15

        self.grid_size = grid_size
        self.difficulty = difficulty
        self.grid = [[0 for _ in range(grid_size)] for _ in range(grid_size)]
        self.entrance = None
        self.exit = None

    def generate(self):
        # Generate dungeon layout based on difficulty
        room_target, deadend_chance = self._get_difficulty_params()

        # Entrance on left edge, exit on right edge
        self.entrance = (0, random.randint(0, self.grid_size-1))
        self.exit = (self.grid_size-1, random.randint(0, self.grid_size-1))

        # Guaranteed path between entrance & exit
        path = self._carve_main_path(self.entrance, self.exit)
        for x, y in path:
            self.grid[y][x] = 1

        carved = len(path)

        # Create additional rooms until we hit the target
        while carved < room_target:
            x = random.randint(0, self.grid_size-1)
            y = random.randint(0, self.grid_size-1)

            if self.grid[y][x] == 1:  # already a room
                continue

            # ensure new room connects to an existing one
            if self._has_adjacent_room(x, y):
                self.grid[y][x] = 1
                carved += 1

                # chance to make small branches/deadends
                if random.random() < deadend_chance:
                    self._carve_deadend((x, y))
        # Build a dictionary of room coordinates for easy access
        self.rooms = {}
        for y in range(self.grid_size):
            for x in range(self.grid_size):
                if self.grid[y][x] == 1:
                    # Store a simple placeholder Rect 
                    self.rooms[(x, y)] = pygame.Rect(x * 64, y * 64, 64, 64)            

    def _carve_main_path(self, start, end):
        # Carve a simple randomized path from start to end
        (x, y) = start
        (ex, ey) = end
        path = [(x, y)]
        while (x, y) != (ex, ey):
            if random.random() < 0.5:  # prefer horizontal
                if x < ex: x += 1
                elif x > ex: x -= 1
            else:
                if y < ey: y += 1
                elif y > ey: y -= 1
            path.append((x, y))
        return path

    def _carve_deadend(self, pos, length=3):
        # Create short branching deadend tunnels
        x, y = pos
        for _ in range(length):
            direction = random.choice([(1,0),(-1,0),(0,1),(0,-1)])
            x += direction[0]
            y += direction[1]
            if 0 <= x < self.grid_size and 0 <= y < self.grid_size:
                self.grid[y][x] = 1

    def _has_adjacent_room(self, x, y):
        # Check if a cell is next to an existing room
        for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < self.grid_size and 0 <= ny < self.grid_size:
                if self.grid[ny][nx] == 1:
                    return True
        return False

    def _get_difficulty_params(self):
        # Return (room_target, deadend_chance) for each difficulty
        size = self.grid_size * self.grid_size
        if self.difficulty == "easy":
            return (int(size * 0.15), 0.1)   # ~15% of grid = small dungeon
        elif self.difficulty == "normal":
            return (int(size * 0.25), 0.2)   # ~25%
        elif self.difficulty == "hard":
            return (int(size * 0.35), 0.3)   # ~35%
        elif self.difficulty == "legendary":
            return (int(size * 0.5), 0.4)    # ~50% → sprawling
        else:
            return (int(size * 0.25), 0.2)   # default = normal

    def print_dungeon(self):
        # Print dungeon to console for debugging
        for y in range(self.grid_size):
            row = ""
            for x in range(self.grid_size):
                if (x, y) == self.entrance:
                    row += "S"
                elif (x, y) == self.exit:
                    row += "E"
                elif self.grid[y][x] == 1:
                    row += "."
                else:
                    row += "#"
            print(row)
