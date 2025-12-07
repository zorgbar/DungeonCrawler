import pygame, sys
from game import Game

if __name__ == "__main__":
    pygame.init()
    game = Game()
    game.run()
    pygame.quit()
    sys.exit()
