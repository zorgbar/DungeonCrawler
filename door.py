import pygame
import os

ASSET_DIR = os.path.join(os.path.dirname(__file__), "assets")

class Door:
    def __init__(self, rect, leads_to, sprite=None):
        self.rect = rect
        self.leads_to = leads_to
        self.image = None

        if sprite:
            try:
                self.image = pygame.transform.scale(sprite, (rect.width, rect.height))
            except Exception as e:
                print(f"⚠️ Failed to assign door sprite: {e}")
                self.image = None

    def draw(self, surface, camera_offset):
        draw_rect = self.rect.move(-camera_offset[0], -camera_offset[1])
        if self.image:
            # Center sprite within rect
            surface.blit(self.image, (draw_rect.centerx - self.image.get_width() // 2,
                                      draw_rect.centery - self.image.get_height() // 2))
        else:
            color = (180, 180, 180)
            pygame.draw.rect(surface, color, draw_rect)
