import pygame


class Ball:
    def __init__(self, x, y, radius=8):
        self.x = float(x)
        self.y = float(y)
        self.radius = radius
        self.vx = 0.0
        self.vy = 0.0

    def move(self):
        self.x += self.vx
        self.y += self.vy

    def rect(self):
        return pygame.Rect(
            round(self.x - self.radius),
            round(self.y - self.radius),
            self.radius * 2,
            self.radius * 2,
        )
