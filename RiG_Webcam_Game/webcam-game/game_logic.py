"""Pure game rules for Hand Dodge+. No camera or graphics libraries required."""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import random


DIFFICULTIES = {
    # Spawn interval, obstacle speed, initial lives, seconds per level
    "easy":   {"interval": 1.32, "speed": 0.80, "lives": 5, "level_sec": 25},
    "normal": {"interval": 1.05, "speed": 1.00, "lives": 3, "level_sec": 20},
    "hard":   {"interval": 0.79, "speed": 1.24, "lives": 2, "level_sec": 16},
}


@dataclass
class Obstacle:
    x: float
    y: float
    width: int
    height: int
    speed: float


@dataclass
class Pickup:
    x: float
    y: float
    radius: int
    speed: float
    kind: str = "star"  # star = bonus points, shield = one safe hit


@dataclass
class Game:
    width: int = 900
    height: int = 620
    seed: int | None = None
    difficulty: str = "normal"
    best_score: int = 0
    player_width: int = 60
    player_height: int = 30
    player_x: float = field(init=False)
    player_y: float = field(init=False)
    score: int = field(default=0, init=False)
    lives: int = field(init=False)
    level: int = field(default=1, init=False)
    combo: int = field(default=0, init=False)
    max_combo: int = field(default=0, init=False)
    dodges: int = field(default=0, init=False)
    elapsed: float = field(default=0.0, init=False)
    spawn_timer: float = field(default=0.0, init=False)
    pickup_timer: float = field(default=0.0, init=False)
    score_clock: float = field(default=0.0, init=False)
    hit_cooldown: float = field(default=0.0, init=False)
    shield_time: float = field(default=0.0, init=False)
    notice: str = field(default="", init=False)
    notice_timer: float = field(default=0.0, init=False)
    level_flash_timer: float = field(default=0.0, init=False)
    game_over: bool = field(default=False, init=False)
    obstacles: list[Obstacle] = field(default_factory=list, init=False)
    pickups: list[Pickup] = field(default_factory=list, init=False)
    rng: random.Random = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.difficulty not in DIFFICULTIES:
            raise ValueError(f"Unknown difficulty: {self.difficulty}")
        self.rng = random.Random(self.seed)
        self.reset()

    @property
    def settings(self) -> dict:
        return DIFFICULTIES[self.difficulty]

    @property
    def multiplier(self) -> int:
        # x1 for 0-3 consecutive dodges, x2 for 4-7, x3 for 8-11...
        return min(4, 1 + self.combo // 4)

    @property
    def spawn_interval(self) -> float:
        return max(0.37, self.settings["interval"] * (0.91 ** (self.level - 1)))

    def reset(self) -> None:
        self.player_x = self.width / 2
        self.player_y = self.height - 74
        self.score = 0
        self.lives = self.settings["lives"]
        self.level = 1
        self.combo = 0
        self.max_combo = 0
        self.dodges = 0
        self.elapsed = 0.0
        self.spawn_timer = 0.0
        self.pickup_timer = 0.0
        self.score_clock = 0.0
        self.hit_cooldown = 0.0
        self.shield_time = 0.0
        self.notice = "MOVE YOUR HAND TO DODGE!"
        self.notice_timer = 3.0
        self.level_flash_timer = 0.0
        self.game_over = False
        self.obstacles = []
        self.pickups = []

    @staticmethod
    def collides(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
        ax, ay, aw, ah = a
        bx, by, bw, bh = b
        return ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by

    def tell(self, message: str, duration: float = 1.3) -> None:
        self.notice = message
        self.notice_timer = duration

    def spawn(self) -> None:
        size = self.rng.randint(32, 62)
        x = self.rng.uniform(12, max(12, self.width - size - 12))
        speed = (155 + (self.level - 1) * 30 + self.rng.uniform(-12, 45)) * self.settings["speed"]
        self.obstacles.append(Obstacle(x, -size, size, size, speed))

    def spawn_pickup(self) -> None:
        kind = "shield" if self.rng.random() < 0.24 else "star"
        radius = 17 if kind == "shield" else 15
        x = self.rng.uniform(28, self.width - 28)
        speed = 130 + (self.level - 1) * 12
        self.pickups.append(Pickup(x, -radius, radius, speed, kind))

    def _damage(self) -> None:
        self.combo = 0
        self.hit_cooldown = 1.1
        if self.shield_time > 0:
            self.shield_time = 0
            self.tell("SHIELD BLOCKED A HIT!", 1.8)
            return
        self.lives -= 1
        if self.lives <= 0:
            self.lives = 0
            self.game_over = True
            self.tell("GAME OVER", 2.0)
        else:
            self.tell("OUCH! COMBO RESET", 1.5)

    def update(self, dt: float, hand_x: float | None) -> None:
        """Advance by dt seconds. Hand disappearance pauses EVERYTHING, including score."""
        if hand_x is None or self.game_over:
            return
        dt = min(max(float(dt), 0.0), 0.1)
        target = min(max(float(hand_x), 0.0), 1.0) * self.width
        alpha = 1 - math.exp(-dt / 0.07)
        self.player_x += (target - self.player_x) * alpha
        self.player_x = min(max(self.player_x, self.player_width / 2), self.width - self.player_width / 2)

        self.elapsed += dt
        self.hit_cooldown = max(0.0, self.hit_cooldown - dt)
        self.shield_time = max(0.0, self.shield_time - dt)
        self.notice_timer = max(0.0, self.notice_timer - dt)
        self.level_flash_timer = max(0.0, self.level_flash_timer - dt)

        new_level = min(10, 1 + int(self.elapsed / self.settings["level_sec"]))
        if new_level > self.level:
            self.level = new_level
            self.level_flash_timer = 2.0
            self.tell(f"LEVEL {self.level}! SPEED UP!", 2.0)

        # Survival awards steadily increase even when no rock reaches the bottom yet.
        self.score_clock += dt
        while self.score_clock >= 1.0 - 1e-9:
            self.score_clock = max(0.0, self.score_clock - 1.0)
            self.score += self.level

        self.spawn_timer += dt
        if self.spawn_timer >= self.spawn_interval:
            self.spawn_timer -= self.spawn_interval
            self.spawn()

        self.pickup_timer += dt
        if self.pickup_timer >= 8.0:
            self.pickup_timer -= 8.0
            self.spawn_pickup()

        player_box = (self.player_x - self.player_width / 2,
                      self.player_y - self.player_height / 2,
                      self.player_width, self.player_height)
        remaining = []
        for index, rock in enumerate(self.obstacles):
            rock.y += rock.speed * dt
            rock_box = (rock.x, rock.y, rock.width, rock.height)
            if self.hit_cooldown <= 0 and self.collides(player_box, rock_box):
                self._damage()
                if self.game_over:
                    remaining.extend(self.obstacles[index + 1:])
                    break
                continue
            if rock.y > self.height:
                self.dodges += 1
                self.combo += 1
                self.max_combo = max(self.max_combo, self.combo)
                points = 10 * self.level * self.multiplier
                self.score += points
                if self.combo % 4 == 0:
                    self.tell(f"{self.combo} COMBO! x{self.multiplier}", 1.3)
                else:
                    self.tell(f"DODGE +{points}", 0.65)
            else:
                remaining.append(rock)
        self.obstacles = remaining

        if self.game_over:
            return

        remaining_pickups = []
        for pickup in self.pickups:
            pickup.y += pickup.speed * dt
            pickup_box = (pickup.x - pickup.radius, pickup.y - pickup.radius,
                          pickup.radius * 2, pickup.radius * 2)
            if self.collides(player_box, pickup_box):
                if pickup.kind == "shield":
                    self.shield_time = 12.0
                    self.tell("SHIELD READY!", 1.7)
                else:
                    points = 40 * self.level
                    self.score += points
                    self.tell(f"STAR BONUS +{points}", 1.5)
            elif pickup.y <= self.height + pickup.radius:
                remaining_pickups.append(pickup)
        self.pickups = remaining_pickups
