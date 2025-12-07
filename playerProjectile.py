import pygame
import math

class PlayerProjectile(pygame.sprite.Sprite):
    def __init__(self, player, target_x, target_y, damage=10, speed=10, color=(255,255,255), radius=5):
        super().__init__()
        self.image = pygame.Surface((radius*2, radius*2), pygame.SRCALPHA)
        pygame.draw.circle(self.image, color, (radius, radius), radius)
        self.rect = self.image.get_rect(center=player.rect.center)
        self.pos = pygame.Vector2(self.rect.center)
        self.damage = damage
        self.speed = speed
        self.color = color
        self.lifetime = 120
        self.on_hit = None

        # Compute direction toward target
        dx = target_x - self.rect.centerx
        dy = target_y - self.rect.centery
        dist = math.hypot(dx, dy)
        if dist != 0:
            self.vel = pygame.Vector2(dx / dist * speed, dy / dist * speed)
        else:
            self.vel = pygame.Vector2(speed, 0)

    def update(self):
        self.pos += self.vel
        self.rect.center = self.pos
        self.lifetime -= 1
        if self.lifetime <= 0:
            self.kill()
