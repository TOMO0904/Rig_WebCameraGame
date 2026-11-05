"""Webcam-only hand-controlled dodge game using OpenCV + MediaPipe Tasks.

Game input is *only* the X position of a hand. Keyboard Q/Esc closes the window;
no keyboard or mouse is needed to play or restart.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path
import sys
import time

import cv2
import numpy as np
from game_logic import Game, Obstacle, Pickup

ROOT=Path(__file__).resolve().parent
MODEL_PATH=ROOT/"models"/"hand_landmarker.task"


class HandTracker:
    """Keep MediaPipe optional so --demo and --snapshot run without it."""
    def __init__(self,model: Path):
        try:
            import mediapipe as mp
        except ImportError as exc:
            raise RuntimeError("MediaPipe not installed. Run: pip install -r requirements.txt") from exc
        if not model.is_file():
            raise FileNotFoundError(f"Model not found: {model}. Run python download_model.py first.")
        # Load in Python before crossing into MediaPipe's native Windows library.
        # This supports model files under OneDrive paths with Japanese characters.
        try:
            model_bytes = model.read_bytes()
        except OSError as exc:
            raise RuntimeError(f"Cannot read model file: {model}: {exc}") from exc
        if len(model_bytes) < 1_000_000:
            raise RuntimeError(
                f"Model file is incomplete ({len(model_bytes)} bytes): {model}. "
                "Delete it and run python download_model.py to download again."
            )
        self.mp=mp
        options=mp.tasks.vision.HandLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_buffer=model_bytes),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_hands=1,
            min_hand_detection_confidence=0.5,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self.landmarker=mp.tasks.vision.HandLandmarker.create_from_options(options)
        self.last_ms=-1
        self.start=time.monotonic()

    def detect(self,frame_bgr: np.ndarray) -> tuple[float | None, list[tuple[int,int]]]:
        h,w=frame_bgr.shape[:2]
        rgb=cv2.cvtColor(frame_bgr,cv2.COLOR_BGR2RGB)
        image=self.mp.Image(image_format=self.mp.ImageFormat.SRGB,data=np.ascontiguousarray(rgb))
        ts=max(self.last_ms+1,int((time.monotonic()-self.start)*1000))
        self.last_ms=ts
        result=self.landmarker.detect_for_video(image,ts)
        if not result.hand_landmarks:
            return None,[]
        points=result.hand_landmarks[0]
        # Track palm center rather than fingertip for less jitter.
        palm_x=sum(points[i].x for i in (0,5,9,13,17))/5
        pixel_points=[(int(p.x*w),int(p.y*h)) for p in points]
        return min(max(palm_x,0.0),1.0),pixel_points

    def close(self) -> None:
        self.landmarker.close()


def draw_camera_preview(frame: np.ndarray | None,points: list[tuple[int,int]],size=(235,177)) -> np.ndarray:
    w,h=size
    if frame is None:
        preview=np.full((h,w,3),(40,38,33),dtype=np.uint8)
        cv2.putText(preview,"DEMO MODE",(44,h//2),cv2.FONT_HERSHEY_SIMPLEX,.6,(255,255,255),2,cv2.LINE_AA)
        return preview
    fh,fw=frame.shape[:2]
    preview=cv2.resize(frame,(w,h))
    connections=[(0,1),(1,2),(2,3),(3,4),(0,5),(5,6),(6,7),(7,8),(5,9),(9,10),(10,11),(11,12),(9,13),(13,14),(14,15),(15,16),(13,17),(17,18),(18,19),(19,20),(0,17)]
    px=[(int(x*w/fw),int(y*h/fh)) for x,y in points]
    for a,b in connections:
        if len(px)>max(a,b):
            cv2.line(preview,px[a],px[b],(0,230,130),2,cv2.LINE_AA)
    for p in px:
        cv2.circle(preview,p,3,(0,220,255),-1,cv2.LINE_AA)
    return preview


def draw_game(game: Game, preview: np.ndarray | None = None, status: str = "TRACKING",
              hold_progress: float = 0.0, highscore: int | None = None) -> np.ndarray:
    """Render the arcade game, including dynamic difficulty and score feedback."""
    w, h = game.width, game.height
    canvas = np.full((h, w, 3), (33, 23, 15), dtype=np.uint8)
    t = game.elapsed

    # Moving star field. Rendering is deterministic and never alters game rules.
    for i in range(100):
        x = (i * 173 + 71) % w
        y = int((i * 103 + t * (12 + i % 4 * 8)) % (h - 100)) + 90
        lum = 55 + (i * 29) % 100
        cv2.circle(canvas, (x, y), 1 if i % 5 else 2, (lum, lum, lum), -1)

    # Falling blocks are bright and have a small speed trail.
    for rock in game.obstacles:
        x, y, rw, rh = int(rock.x), int(rock.y), int(rock.width), int(rock.height)
        cv2.line(canvas, (x + rw // 2, y - 22), (x + rw // 2, y),
                 (53, 78, 106), 2, cv2.LINE_AA)
        cv2.rectangle(canvas, (x, y), (x + rw, y + rh), (50, 95, 237), -1)
        cv2.rectangle(canvas, (x + 4, y + 4), (x + rw - 4, y + rh - 4),
                      (77, 174, 255), 2)
        cv2.line(canvas, (x + 10, y + 10), (x + rw - 10, y + rh - 10),
                 (180, 218, 255), 2, cv2.LINE_AA)

    # Collectables: yellow diamonds for bonus points, cyan circles for shield.
    for pickup in game.pickups:
        x, y, r = int(pickup.x), int(pickup.y), pickup.radius
        if pickup.kind == "shield":
            cv2.circle(canvas, (x, y), r + 3, (250, 210, 45), 2, cv2.LINE_AA)
            cv2.circle(canvas, (x, y), r - 3, (245, 180, 60), -1, cv2.LINE_AA)
            cv2.putText(canvas, "S", (x - 8, y + 7), cv2.FONT_HERSHEY_SIMPLEX,
                        .65, (30, 37, 25), 2, cv2.LINE_AA)
        else:
            diamond = np.array([(x, y-r), (x+r, y), (x, y+r), (x-r, y)], np.int32)
            cv2.fillConvexPoly(canvas, diamond, (38, 221, 255), lineType=cv2.LINE_AA)
            cv2.circle(canvas, (x, y), 4, (250, 250, 255), -1, cv2.LINE_AA)

    px, py = int(game.player_x), int(game.player_y)
    if game.shield_time > 0:
        cv2.circle(canvas, (px, py), 49, (235, 208, 38), 3, cv2.LINE_AA)
        cv2.circle(canvas, (px, py), 43, (142, 114, 21), 1, cv2.LINE_AA)
    flashing = game.hit_cooldown > 0 and int(game.hit_cooldown * 12) % 2 == 1
    ship_color = (85, 132, 100) if flashing else (96, 255, 152)
    ship = np.array([(px, py-26), (px-31, py+18), (px, py+10), (px+31, py+18)], np.int32)
    cv2.fillConvexPoly(canvas, ship, ship_color, lineType=cv2.LINE_AA)
    cv2.line(canvas, (px, py-20), (px, py+9), (255, 255, 255), 2, cv2.LINE_AA)

    # HUD: visible during gameplay, camera and pause overlays.
    cv2.rectangle(canvas, (0, 0), (w, 92), (40, 34, 27), -1)
    cv2.putText(canvas, "HAND DODGE+", (18, 35), cv2.FONT_HERSHEY_SIMPLEX,
                .85, (245, 236, 177), 2, cv2.LINE_AA)
    cv2.putText(canvas, game.difficulty.upper(), (21, 61), cv2.FONT_HERSHEY_SIMPLEX,
                .5, (175, 194, 223), 1, cv2.LINE_AA)
    cv2.putText(canvas, f"SCORE {game.score:05d}", (233, 32), cv2.FONT_HERSHEY_SIMPLEX,
                .72, (245, 245, 245), 2, cv2.LINE_AA)
    best = max(game.best_score, game.score) if highscore is None else max(highscore, game.score)
    cv2.putText(canvas, f"BEST {best:05d}", (237, 58), cv2.FONT_HERSHEY_SIMPLEX,
                .54, (190, 206, 221), 1, cv2.LINE_AA)
    cv2.putText(canvas, f"LIVES {game.lives}", (477, 34), cv2.FONT_HERSHEY_SIMPLEX,
                .70, (135, 233, 178), 2, cv2.LINE_AA)
    cv2.putText(canvas, f"LV {game.level}", (675, 34), cv2.FONT_HERSHEY_SIMPLEX,
                .70, (88, 215, 255), 2, cv2.LINE_AA)
    cv2.putText(canvas, f"COMBO {game.combo}  x{game.multiplier}", (475, 61),
                cv2.FONT_HERSHEY_SIMPLEX, .49, (90, 217, 255), 1, cv2.LINE_AA)

    # Next level progress under HUD.
    level_span = game.settings["level_sec"]
    progress = (game.elapsed % level_span) / level_span if game.level < 10 else 1.0
    cv2.rectangle(canvas, (0, 87), (w, 91), (70, 73, 72), -1)
    cv2.rectangle(canvas, (0, 87), (int(w * progress), 91), (70, 201, 255), -1)

    if game.notice_timer > 0 and not game.game_over and status == "TRACKING":
        color = (100, 235, 255) if "BONUS" in game.notice or "COMBO" in game.notice else (159, 241, 189)
        text_width = cv2.getTextSize(game.notice, cv2.FONT_HERSHEY_SIMPLEX, .76, 2)[0][0]
        cv2.putText(canvas, game.notice, ((w-text_width)//2, 180),
                    cv2.FONT_HERSHEY_SIMPLEX, .76, color, 2, cv2.LINE_AA)

    if game.level_flash_timer > 0 and status == "TRACKING":
        cv2.rectangle(canvas, (2, 94), (w-3, h-53), (67, 180, 246), 3)

    # Bottom HUD with instructions and power-up countdown.
    cv2.rectangle(canvas, (0, h-49), (w, h), (42, 33, 26), -1)
    cv2.putText(canvas, "HAND LEFT / RIGHT TO MOVE", (18, h-20),
                cv2.FONT_HERSHEY_SIMPLEX, .53, (188, 211, 225), 1, cv2.LINE_AA)
    shield_label = f"SHIELD {game.shield_time:.0f}s" if game.shield_time > 0 else "CATCH STARS + SHIELDS"
    cv2.putText(canvas, shield_label, (510, h-20), cv2.FONT_HERSHEY_SIMPLEX,
                .53, (168, 226, 251), 1, cv2.LINE_AA)

    if preview is not None:
        ph, pw = preview.shape[:2]
        x, y = w-pw-18, 108
        canvas[y:y+ph, x:x+pw] = preview
        cv2.rectangle(canvas, (x-1, y-1), (x+pw, y+ph), (126, 193, 244), 2)
        cv2.putText(canvas, "LIVE HAND", (x+4, y+ph+18), cv2.FONT_HERSHEY_SIMPLEX,
                    .41, (191, 218, 229), 1, cv2.LINE_AA)

    if status != "TRACKING" or game.game_over:
        # Preserve camera preview while dimming only the middle portion.
        overlay = canvas.copy()
        cv2.rectangle(overlay, (145, 258), (w-145, 435), (26, 29, 39), -1)
        canvas = cv2.addWeighted(overlay, .9, canvas, .1, 0)
        headline = "GAME OVER" if game.game_over else ("PAUSED" if status == "PAUSED" else "READY?")
        subtitle = ("HOLD HAND IN CENTER TO RESTART" if game.game_over
                    else "SHOW ONE HAND TO CONTINUE")
        headline_width = cv2.getTextSize(headline, cv2.FONT_HERSHEY_SIMPLEX, 1.25, 3)[0][0]
        cv2.putText(canvas, headline, ((w-headline_width)//2, 325),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.25, (255, 250, 243), 3, cv2.LINE_AA)
        sub_width = cv2.getTextSize(subtitle, cv2.FONT_HERSHEY_SIMPLEX, .6, 2)[0][0]
        cv2.putText(canvas, subtitle, ((w-sub_width)//2, 363),
                    cv2.FONT_HERSHEY_SIMPLEX, .6, (187, 246, 230), 2, cv2.LINE_AA)
        if game.game_over:
            cv2.putText(canvas, f"SCORE {game.score}  |  MAX COMBO {game.max_combo}",
                        (268, 396), cv2.FONT_HERSHEY_SIMPLEX, .54, (245, 230, 170), 1, cv2.LINE_AA)
            cv2.rectangle(canvas, (200, 416), (700, 427), (178, 180, 182), 1)
            cv2.rectangle(canvas, (200, 416), (200+int(500*min(1,max(0,hold_progress))),427),
                          (125, 237, 173), -1)

    return canvas


def snapshot(path: Path, difficulty: str = "normal") -> None:
    game = Game(seed=2026, difficulty=difficulty)
    game.score = 1250
    game.combo = 7
    game.level = 3
    game.shield_time = 6.5
    game.obstacles = [Obstacle(175, 160, 55, 55, 230),
                      Obstacle(430, 275, 58, 58, 240),
                      Obstacle(680, 345, 45, 45, 220)]
    game.pickups = [Pickup(300, 265, 16, 150, "star"),
                    Pickup(570, 340, 17, 150, "shield")]
    image = draw_game(game, draw_camera_preview(None, [], (175, 132)))
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), image):
        raise RuntimeError(f"Could not save preview to {path}")
    print(f"Saved preview: {path.resolve()}")


def load_high_scores(path: Path) -> dict[str, int]:
    import json
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    return {name: max(0, int(raw.get(name, 0))) if str(raw.get(name, 0)).isdigit() else 0
            for name in ("easy", "normal", "hard")}


def save_high_scores(path: Path, scores: dict[str, int]) -> None:
    import json
    import os
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(scores, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def open_windows_webcam(camera_id: int):
    """Open a Windows built-in or USB webcam with a usable video backend.

    DirectShow and Media Foundation expose different devices/drivers, so
    retry both if one opens the handle but cannot deliver video frames.
    """
    candidates = (
        [(cv2.CAP_DSHOW, "DirectShow"), (cv2.CAP_MSMF, "Media Foundation"),
         (cv2.CAP_ANY, "default")]
        if sys.platform == "win32" else [(cv2.CAP_ANY, "default")]
    )
    for backend, label in candidates:
        cap = cv2.VideoCapture(camera_id, backend)
        if not cap.isOpened():
            cap.release()
            continue
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        # Some webcams need a little warm-up time for the first frame.
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline:
            ok, frame = cap.read()
            if ok and frame is not None and frame.size:
                print(f"Using webcam {camera_id} via {label}")
                return cap, frame
            time.sleep(0.08)
        cap.release()
    raise RuntimeError(
        f"Windows webcam {camera_id} was not readable. "
        "Close the Windows Camera / Zoom / Teams apps, enable camera privacy "
        "permissions for desktop apps, or try camera index 1."
    )


def run(camera_id: int, demo: bool, model: Path, difficulty: str = "normal") -> None:
    cap = None
    tracker = None
    first_frame = None
    if not demo:
        cap, first_frame = open_windows_webcam(camera_id)
        try:
            tracker = HandTracker(model)
        except Exception:
            cap.release()
            raise
    scores_path = ROOT / "highscores.json"
    high_scores = load_high_scores(scores_path)
    game = Game(seed=None, difficulty=difficulty, best_score=high_scores[difficulty])
    game_name = "RiG++ | HAND DODGE+ (Q to quit)"
    previous = time.monotonic()
    begin = previous
    restart_start = None
    record_saved = False

    def store_record():
        nonlocal record_saved
        if game.score > high_scores[difficulty]:
            high_scores[difficulty] = game.score
            try:
                save_high_scores(scores_path, high_scores)
                print(f"Saved {difficulty} high score: {game.score}")
            except OSError as error:
                print(f"Warning: Could not save high score: {error}")
        record_saved = True

    try:
        cv2.namedWindow(game_name, cv2.WINDOW_NORMAL)
        while True:
            now = time.monotonic()
            dt = min(now-previous, .10)
            previous = now
            hand = None
            landmarks = []
            frame = None
            if demo:
                hand = .5 + .43 * math.sin((now-begin)*1.1)
            else:
                assert cap is not None and tracker is not None
                if first_frame is not None:
                    raw = first_frame
                    first_frame = None
                    ok = True
                else:
                    ok, raw = cap.read()
                if not ok or raw is None:
                    raise RuntimeError("Camera stopped returning frames. Reopen or try camera 1.")
                frame = cv2.flip(raw, 1)
                hand, landmarks = tracker.detect(frame)
            if game.game_over:
                if not record_saved:
                    store_record()
                if hand is not None and .40 <= hand <= .60:
                    if restart_start is None:
                        restart_start = now
                    if now-restart_start >= 1.5:
                        game.reset()
                        game.best_score = high_scores[difficulty]
                        record_saved = False
                        restart_start = None
                else:
                    restart_start = None
            else:
                game.update(dt, hand)
            cam = draw_camera_preview(frame, landmarks, (175, 132))
            status = ("GAME_OVER" if game.game_over else
                      "PAUSED" if hand is None and game.elapsed > 0 else
                      "START" if hand is None else "TRACKING")
            progress = 0 if restart_start is None else min(1.0, (now-restart_start)/1.5)
            view = draw_game(game, cam, status, progress, high_scores[difficulty])
            cv2.imshow(game_name, view)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
    finally:
        if not record_saved and game.score > high_scores[difficulty]:
            store_record()
        if tracker is not None:
            tracker.close()
        if cap is not None:
            cap.release()
        cv2.destroyAllWindows()


def main() -> None:
    parser = argparse.ArgumentParser(description="Hand Dodge+ with combos, levels and bonus items")
    parser.add_argument("--camera", type=int, default=0, help="camera index (default 0)")
    parser.add_argument("--model", type=Path, default=MODEL_PATH, help="Hand Landmarker .task path")
    parser.add_argument("--difficulty", choices=("easy", "normal", "hard"), default="normal")
    parser.add_argument("--demo", action="store_true", help="Autoplay without webcam/MediaPipe")
    parser.add_argument("--snapshot", type=Path, help="Write screenshot and exit")
    args = parser.parse_args()
    try:
        if args.snapshot:
            snapshot(args.snapshot, args.difficulty)
        else:
            run(args.camera, args.demo, args.model, args.difficulty)
    except (RuntimeError, FileNotFoundError, OSError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
