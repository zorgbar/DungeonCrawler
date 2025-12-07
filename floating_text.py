import pygame

class FloatingText(pygame.sprite.Sprite):
    def __init__(self, text, x, y, color=(255, 0, 0), lifetime=30):
        super().__init__()
        font = pygame.font.SysFont("Arial", 18, bold=True)
        self.image = font.render(str(text), True, color)
        self.rect = self.image.get_rect(center=(x, y))

        self.lifetime = lifetime   # how many frames it stays
        self.velocity_y = -1       # float upwards slowly
        self.alpha = 255           # fade out

    def update(self):
        self.rect.y += self.velocity_y
        self.lifetime -= 1
        if self.lifetime <= 0:
            self.kill()
        else:
            # Fade effect
            self.alpha = max(0, int(255 * (self.lifetime / 30)))
            self.image.set_alpha(self.alpha)
