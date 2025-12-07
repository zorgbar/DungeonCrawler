import pygame
import os

class SoundManager:
    def __init__(self, base_path="assets/sounds"):
        self.sounds = {}
        self.base_path = base_path

    def load(self, name, filepath, volume=1.0):
        # Make sure path is relative to the game directory
        base_path = os.path.dirname(os.path.abspath(__file__))
        full_path = os.path.join(base_path, filepath)

        if not os.path.exists(full_path):
            print(f"Missing sound: {full_path}")
            return

        sound = pygame.mixer.Sound(full_path)
        sound.set_volume(volume)
        self.sounds[name] = sound

    def play(self, name):
        if name in self.sounds:
            self.sounds[name].play()

    def stop(self, name):
        if name in self.sounds:
            self.sounds[name].stop()

    def play_music(self, filepath, volume=0.5, loop=-1):
        base_path = os.path.dirname(os.path.abspath(__file__))
        full_path = os.path.join(base_path, filepath)

        if not os.path.exists(full_path):
            print(f"Missing music: {full_path}")
            return

        pygame.mixer.music.load(full_path)
        pygame.mixer.music.set_volume(volume)
        pygame.mixer.music.play(loop)

    def stop_music(self):
        pygame.mixer.music.stop()