"""Preview built-in/USB webcams on Windows before starting the game."""
from __future__ import annotations
import argparse
import cv2
from main import open_windows_webcam


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--camera', type=int, default=0)
    args=parser.parse_args()
    cap, first_frame = open_windows_webcam(args.camera)
    try:
        title = f"Windows webcam {args.camera} | press Q or Esc to close"
        cv2.namedWindow(title, cv2.WINDOW_NORMAL)
        pending = first_frame
        while True:
            if pending is not None:
                frame, pending = pending, None
            else:
                ok, frame = cap.read()
                if not ok or frame is None:
                    raise RuntimeError('Webcam stopped returning frames')
            cv2.imshow(title, cv2.flip(frame, 1))
            if cv2.waitKey(1) & 0xFF in (ord('q'), 27):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()

if __name__ == '__main__':
    main()
