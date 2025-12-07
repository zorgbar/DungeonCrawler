import pygame
import math
from floating_text import FloatingText

# Enemy Projectile Class
class Projectile(pygame.sprite.Sprite):
    def __init__(self, x, y, target, damage, floating_group=None, speed=6, color=(200, 50, 50), radius=5):
        super().__init__()
        self.image = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(self.image, color, (radius, radius), radius)
        self.rect = self.image.get_rect(center=(x, y))
        self.target = target
        self.damage = damage
        self.speed = speed
        self.floating_group = floating_group

        # Compute normalized direction vector toward target
        dx = target.rect.centerx - x
        dy = target.rect.centery - y
        dist = math.hypot(dx, dy)
        if dist == 0:
            dist = 1
        self.vel_x = dx / dist * speed
        self.vel_y = dy / dist * speed

    def update(self):
        # Move projectile
        self.rect.x += self.vel_x
        self.rect.y += self.vel_y

        # Update lifetime
        if not hasattr(self, 'lifetime'):
            self.lifetime = 120  # Default lifetime of 2 seconds
        self.lifetime -= 1
        if self.lifetime <= 0:
            self.kill()
            return

        # Check collision with target
        if self.target and self.target.rect.colliderect(self.rect):
            if hasattr(self.target, "take_damage"):
                self.target.take_damage(self.damage, self.floating_group)
            self.kill()
