import math
import pygame
from array import array

from .paddle import Paddle
from .ball import Ball
from .brick import Brick


WHITE = (255, 255, 255)
BG = (15, 15, 25)
PANEL = (25, 25, 40)
GREEN = (80, 220, 120)
RED = (230, 80, 80)
YELLOW = (245, 205, 70)
BLUE = (80, 150, 240)

BRICK_COLORS = [
    (220, 70, 70),
    (235, 135, 60),
    (235, 205, 65),
    (90, 190, 95),
    (85, 145, 220),
]

DIFFICULTIES = {
    "Easy": {"ball_speed": 3.5, "paddle_width": 115, "paddle_speed": 7},
    "Medium": {"ball_speed": 4.5, "paddle_width": 100, "paddle_speed": 7},
    "Hard": {"ball_speed": 6.0, "paddle_width": 85, "paddle_speed": 8},
}


class SoundManager:
    """Small procedural sound effects; no external audio files are required."""

    def __init__(self):
        self.enabled = True
        self.sounds = {}

        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()

            self.sounds["brick"] = self._tone(620, 0.07)
            self.sounds["paddle"] = self._tone(300, 0.05)
            self.sounds["wall"] = self._tone(190, 0.04)
            self.sounds["end"] = self._sequence((440, 660, 880), 0.12)
        except pygame.error:
            self.enabled = False

    @staticmethod
    def _tone(frequency, duration, volume=0.18, sample_rate=44100):
        count = int(sample_rate * duration)
        samples = array(
            "h",
            (
                int(
                    32767
                    * volume
                    * math.sin(2 * math.pi * frequency * i / sample_rate)
                )
                for i in range(count)
            ),
        )
        return pygame.mixer.Sound(buffer=samples.tobytes())

    def _sequence(self, frequencies, duration):
        # A short composite sound used for win/loss feedback.
        sample_rate = 44100
        parts = []
        for frequency in frequencies:
            count = int(sample_rate * duration)
            parts.extend(
                int(
                    32767
                    * 0.16
                    * math.sin(2 * math.pi * frequency * i / sample_rate)
                )
                for i in range(count)
            )
        samples = array("h", parts)
        return pygame.mixer.Sound(buffer=samples.tobytes())

    def play(self, name):
        if self.enabled and name in self.sounds:
            self.sounds[name].play()


class GameEngine:
    def __init__(self, width, height):
        self.width = width
        self.height = height

        self.font = pygame.font.SysFont("Arial", 26)
        self.title_font = pygame.font.SysFont("Arial", 42, bold=True)
        self.small_font = pygame.font.SysFont("Arial", 20)

        self.sound = SoundManager()
        self.difficulty = "Medium"

        self.state = "playing"
        self.result = None
        self._end_sound_played = False

        self.rows, self.cols = 5, 8
        self.lives = 3
        self.score = 0

        self.paddle = None
        self.ball = None
        self.bricks = []
        self.start_game(self.difficulty)

    def start_game(self, difficulty):
        settings = DIFFICULTIES[difficulty]
        self.difficulty = difficulty

        paddle_width = settings["paddle_width"]
        self.paddle = Paddle(
            self.width // 2 - paddle_width // 2,
            self.height - 30,
            paddle_width,
            14,
        )
        self.paddle.speed = settings["paddle_speed"]

        self.ball = Ball(self.width // 2, self.height - 50, radius=8)
        self.lives = 3
        self.score = 0
        self.state = "playing"
        self.result = None
        self._end_sound_played = False

        self.bricks = self._build_bricks(self.rows, self.cols)
        self._reset_ball()

    def _build_bricks(self, rows, cols):
        bricks = []
        margin, gap, top = 30, 6, 60
        brick_w = (self.width - margin * 2 - gap * (cols - 1)) // cols
        brick_h = 22

        for r in range(rows):
            for c in range(cols):
                x = margin + c * (brick_w + gap)
                y = top + r * (brick_h + gap)
                bricks.append(Brick(x, y, brick_w, brick_h))

        return bricks

    def _reset_ball(self):
        speed = DIFFICULTIES[self.difficulty]["ball_speed"]
        self.ball.x = self.width / 2
        self.ball.y = self.height - 50

        # Keep a small horizontal component so the first trajectory is not
        # perfectly vertical.
        direction = -1 if pygame.time.get_ticks() // 1000 % 2 == 0 else 1
        self.ball.vx = direction * speed * 0.72
        self.ball.vy = -speed

    def handle_event(self, event):
        if event.type != pygame.KEYDOWN:
            return

        if self.state == "playing":
            if event.key == pygame.K_ESCAPE or event.key == pygame.K_q:
                self.state = "quit"

        elif self.state in ("win", "lose"):
            if event.key == pygame.K_1:
                self.start_game("Easy")
            elif event.key == pygame.K_2:
                self.start_game("Medium")
            elif event.key == pygame.K_3:
                self.start_game("Hard")
            elif event.key in (pygame.K_ESCAPE, pygame.K_q):
                self.state = "quit"

    def handle_input(self):
        if self.state != "playing":
            return

        keys = pygame.key.get_pressed()

        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.paddle.move(-self.paddle.speed, self.width)

        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.paddle.move(self.paddle.speed, self.width)

    @staticmethod
    def _collision_side(previous_rect, current_rect, target_rect):
        """Return the side of target_rect that was crossed: left/right/top/bottom.

        This uses the ball's previous position plus the current overlap instead
        of always assuming a vertical bounce.
        """
        if previous_rect.right <= target_rect.left and current_rect.right >= target_rect.left:
            return "left"
        if previous_rect.left >= target_rect.right and current_rect.left <= target_rect.right:
            return "right"
        if previous_rect.bottom <= target_rect.top and current_rect.bottom >= target_rect.top:
            return "top"
        if previous_rect.top >= target_rect.bottom and current_rect.top <= target_rect.bottom:
            return "bottom"

        # Corner/very-small overlap fallback: use penetration depth.
        overlap_left = current_rect.right - target_rect.left
        overlap_right = target_rect.right - current_rect.left
        overlap_top = current_rect.bottom - target_rect.top
        overlap_bottom = target_rect.bottom - current_rect.top

        candidates = [
            ("left", overlap_left),
            ("right", overlap_right),
            ("top", overlap_top),
            ("bottom", overlap_bottom),
        ]
        return min((item for item in candidates if item[1] >= 0), key=lambda x: x[1])[0]

    def _bounce_from_paddle(self, previous_rect):
        paddle_rect = self.paddle.rect()
        current_rect = self.ball.rect()
        side = self._collision_side(previous_rect, current_rect, paddle_rect)

        # A side hit on the paddle should reverse horizontal velocity.
        if side in ("left", "right"):
            self.ball.vx *= -1
            if side == "left":
                self.ball.x = paddle_rect.left - self.ball.radius - 1
            else:
                self.ball.x = paddle_rect.right + self.ball.radius + 1
            return

        # Top/bottom paddle collision reverses vertical velocity. For a more
        # natural game feel, the hit position changes the outgoing angle.
        if self.ball.vy > 0:
            offset = (
                (self.ball.x - paddle_rect.centerx)
                / max(1, paddle_rect.width / 2)
            )
            speed = math.hypot(self.ball.vx, self.ball.vy)
            self.ball.vx = speed * max(-0.9, min(0.9, offset))
            self.ball.vy = -math.sqrt(max(1.0, speed * speed - self.ball.vx ** 2))
            self.ball.y = paddle_rect.top - self.ball.radius - 1
            self.sound.play("paddle")

    def _bounce_from_brick(self, brick, previous_rect):
        brick_rect = brick.rect()
        current_rect = self.ball.rect()
        side = self._collision_side(previous_rect, current_rect, brick_rect)

        if side in ("left", "right"):
            self.ball.vx *= -1
            if side == "left":
                self.ball.x = brick_rect.left - self.ball.radius - 1
            else:
                self.ball.x = brick_rect.right + self.ball.radius + 1
        else:
            self.ball.vy *= -1
            if side == "top":
                self.ball.y = brick_rect.top - self.ball.radius - 1
            else:
                self.ball.y = brick_rect.bottom + self.ball.radius + 1

    def update(self):
        if self.state != "playing":
            return

        previous_rect = self.ball.rect()
        self.ball.move()
        current_rect = self.ball.rect()

        # Side walls.
        if self.ball.x - self.ball.radius <= 0:
            self.ball.x = self.ball.radius
            self.ball.vx = abs(self.ball.vx)
            self.sound.play("wall")
        elif self.ball.x + self.ball.radius >= self.width:
            self.ball.x = self.width - self.ball.radius
            self.ball.vx = -abs(self.ball.vx)
            self.sound.play("wall")

        # Top wall.
        if self.ball.y - self.ball.radius <= 0:
            self.ball.y = self.ball.radius
            self.ball.vy = abs(self.ball.vy)
            self.sound.play("wall")

        # Paddle collision.
        if self.ball.vy > 0 and current_rect.colliderect(self.paddle.rect()):
            self._bounce_from_paddle(previous_rect)

        # Brick collision.
        for brick in self.bricks:
            if brick.alive and self.ball.rect().colliderect(brick.rect()):
                self._bounce_from_brick(brick, previous_rect)
                brick.alive = False
                self.score += 1
                self.sound.play("brick")
                break

        # Ball missed paddle.
        if self.ball.y - self.ball.radius > self.height:
            self.lives -= 1

            if self.lives <= 0:
                self._finish("lose")
            else:
                self._reset_ball()

        # All bricks cleared.
        if self.state == "playing" and all(not brick.alive for brick in self.bricks):
            self._finish("win")

    def _finish(self, result):
        self.state = result
        self.result = result

        if not self._end_sound_played:
            self.sound.play("end")
            self._end_sound_played = True

    def render(self, screen):
        screen.fill(BG)

        # Header.
        score_text = self.font.render(f"Score: {self.score}", True, WHITE)
        lives_text = self.font.render(f"Lives: {self.lives}", True, WHITE)
        difficulty_text = self.small_font.render(
            f"Difficulty: {self.difficulty}", True, WHITE
        )

        screen.blit(score_text, (10, 10))
        screen.blit(lives_text, (self.width - 125, 10))
        screen.blit(difficulty_text, (self.width // 2 - 55, 16))

        # Game objects remain visible behind the end overlay.
        pygame.draw.rect(screen, WHITE, self.paddle.rect())
        pygame.draw.circle(
            screen,
            WHITE,
            (int(self.ball.x), int(self.ball.y)),
            self.ball.radius,
        )

        for i, brick in enumerate(self.bricks):
            if brick.alive:
                row = i // self.cols
                color = BRICK_COLORS[row % len(BRICK_COLORS)]
                pygame.draw.rect(screen, color, brick.rect())
                pygame.draw.rect(screen, (255, 255, 255), brick.rect(), 1)

        if self.state in ("win", "lose"):
            self._render_end_screen(screen)

    def _render_end_screen(self, screen):
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 205))
        screen.blit(overlay, (0, 0))

        title = "YOU WIN!" if self.state == "win" else "GAME OVER"
        title_color = GREEN if self.state == "win" else RED

        title_surface = self.title_font.render(title, True, title_color)
        score_surface = self.font.render(
            f"Final Score: {self.score}", True, WHITE
        )
        prompt_surface = self.font.render(
            "Choose a difficulty to play again", True, WHITE
        )

        screen.blit(
            title_surface,
            title_surface.get_rect(center=(self.width // 2, 170)),
        )
        screen.blit(
            score_surface,
            score_surface.get_rect(center=(self.width // 2, 235)),
        )
        screen.blit(
            prompt_surface,
            prompt_surface.get_rect(center=(self.width // 2, 290)),
        )

        options = [
            ("1  Easy", "Slower ball • Wider paddle"),
            ("2  Medium", "Balanced speed • Normal paddle"),
            ("3  Hard", "Faster ball • Smaller paddle"),
        ]

        y = 345
        for label, description in options:
            label_surface = self.font.render(label, True, YELLOW)
            desc_surface = self.small_font.render(description, True, WHITE)
            screen.blit(label_surface, (125, y))
            screen.blit(desc_surface, (275, y + 4))
            y += 45

        exit_surface = self.small_font.render(
            "Press Q or Esc to exit", True, WHITE
        )
        screen.blit(
            exit_surface,
            exit_surface.get_rect(center=(self.width // 2, 510)),
        )
