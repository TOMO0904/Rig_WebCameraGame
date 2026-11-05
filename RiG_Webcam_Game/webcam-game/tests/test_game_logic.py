"""Tests for rules, scoring, difficulty, pause and high-score storage."""
from pathlib import Path
import importlib.util
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from game_logic import Game, Obstacle, Pickup


def test_hand_position_moves_ship():
    game = Game(seed=1)
    old = game.player_x
    for _ in range(30):
        game.update(1/30, .95)
    assert old < game.player_x <= game.width - game.player_width / 2


def test_missing_hand_pauses_all_timers():
    game = Game(seed=2)
    game.update(2.0, None)
    assert game.elapsed == 0 and game.score == 0 and not game.obstacles
    game.update(.5, .5)
    old = (game.score, game.elapsed, game.spawn_timer, game.pickup_timer)
    game.update(9.0, None)
    assert old == (game.score, game.elapsed, game.spawn_timer, game.pickup_timer)


def test_dodge_scores_and_increases_combo():
    game = Game(seed=3)
    game.obstacles = [Obstacle(0, game.height-4, 25, 25, 300)]
    game.update(.1, .5)
    assert game.dodges == 1
    assert game.score == 10
    assert game.combo == 1


def test_combo_multiplier_and_hit_reset():
    game = Game(seed=4)
    for i in range(4):
        game.obstacles = [Obstacle(0, game.height-2, 25, 25, 300)]
        game.update(.1, .5)
    assert game.combo == 4
    assert game.multiplier == 2
    assert game.max_combo == 4
    # Test next dodge gets x2 bonus (20 points).
    before = game.score
    game.obstacles = [Obstacle(0, game.height-2, 25, 25, 300)]
    game.update(.1, .5)
    assert game.score - before == 20
    game.obstacles = [Obstacle(game.player_x-10, game.player_y-10, 30, 30, 0)]
    game.update(.01, .5)
    assert game.combo == 0 and game.lives == 2


def test_collision_cooldown_and_shield():
    game = Game(seed=5)
    game.shield_time = 10.0
    game.obstacles = [Obstacle(game.player_x-10, game.player_y-10, 30, 30, 0)]
    game.update(.01, .5)
    assert game.lives == 3 and game.shield_time == 0
    game.obstacles = [Obstacle(game.player_x-10, game.player_y-10, 30, 30, 0)]
    game.update(.01, .5)
    assert game.lives == 3  # post-hit invulnerability
    game.hit_cooldown = 0
    game.update(.01, .5)
    assert game.lives == 2


def test_star_and_shield_pickups():
    game = Game(seed=6)
    game.pickups = [Pickup(game.player_x, game.player_y, 16, 0, "star")]
    game.update(.01, .5)
    assert game.score == 40
    game.pickups = [Pickup(game.player_x, game.player_y, 17, 0, "shield")]
    game.update(.01, .5)
    assert game.shield_time > 11
    assert not game.pickups


def test_survival_score_and_dynamic_level():
    game = Game(seed=7, difficulty="normal")
    for _ in range(200):
        game.update(.1, .5)
        game.obstacles.clear()  # focus on survival scoring
    assert game.elapsed >= 19.99
    assert game.level == 2
    assert game.score >= 20
    assert game.spawn_interval < 1.05


def test_difficulties_change_speed_lives_and_spawn_rate():
    easy = Game(seed=7, difficulty="easy")
    normal = Game(seed=7, difficulty="normal")
    hard = Game(seed=7, difficulty="hard")
    assert easy.lives == 5 and normal.lives == 3 and hard.lives == 2
    assert easy.spawn_interval > normal.spawn_interval > hard.spawn_interval
    easy.spawn(); normal.spawn(); hard.spawn()
    assert easy.obstacles[0].speed < normal.obstacles[0].speed < hard.obstacles[0].speed


def test_game_over_and_restart():
    game = Game(seed=8, difficulty="hard")
    for _ in range(2):
        game.hit_cooldown = 0
        game.obstacles = [Obstacle(game.player_x-10, game.player_y-10, 30, 30, 0)]
        game.update(.01, .5)
    assert game.game_over and game.lives == 0
    oldscore = game.score
    game.update(2.0, .5)
    assert game.score == oldscore
    game.reset()
    assert game.lives == 2 and not game.game_over and game.combo == 0


def test_rect_edge_does_not_collide():
    assert not Game.collides((0, 0, 10, 10), (10, 0, 5, 5))
    assert Game.collides((0, 0, 10, 10), (9, 0, 5, 5))


def test_no_score_after_fatal_collision():
    game = Game(seed=9, difficulty="hard")
    game.lives = 1
    game.obstacles = [Obstacle(game.player_x-10, game.player_y-10, 30, 30, 0),
                      Obstacle(0, game.height+1, 25, 25, 0)]
    game.update(.01, .5)
    assert game.game_over and game.score == 0


def load_renderer():
    path = Path(__file__).resolve().parents[1] / "main.py"
    spec = importlib.util.spec_from_file_location("rig_webcam_main_plus", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_renderer_snapshot(tmp_path):
    import cv2
    m = load_renderer()
    game = Game(seed=10)
    image = m.draw_game(game, m.draw_camera_preview(None, [], (175, 132)))
    assert image.shape == (game.height, game.width, 3)
    f = tmp_path / "preview.png"
    m.snapshot(f)
    assert cv2.imread(str(f)).shape == (game.height, game.width, 3)


def test_highscore_save_and_load(tmp_path):
    m = load_renderer()
    path = tmp_path / "highscores.json"
    assert m.load_high_scores(path) == {"easy": 0, "normal": 0, "hard": 0}
    scores = {"easy": 100, "normal": 340, "hard": 900}
    m.save_high_scores(path, scores)
    assert m.load_high_scores(path) == scores
    path.write_text("INVALID JSON", encoding="utf-8")
    assert m.load_high_scores(path)["normal"] == 0
