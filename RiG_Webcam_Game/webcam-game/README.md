# HAND DODGE+ — RiG++ Advent Calendar 2026

Windows PCのWebカメラで手の位置を認識する落下物よけゲーム。Python 3.13.5のユーザー環境で起動が確認された旧版を基に、スコア・コンボ・3段階の難易度・拾えるアイテムを追加しました。

## 起動

- `start-game-difficulty-menu.bat`：番号でEASY / NORMAL / HARDを選択
- `start-webcam-game.bat`：NORMAL
- `start-webcam-easy.bat`：EASY（初回はNORMALを起動して仮想環境を準備）
- `start-webcam-hard.bat`：HARD（同上）
- `start-webcam-check.bat`：カメラ映像の確認
- `start-webcam-demo.bat`：Webカメラを使用しない自動プレイ

既存のPython 3.9〜3.14 (64bit) を利用し、仮想環境 `.venv-existing` に依存パッケージを入れます。初回は `download_model.py` によりGoogle公式のHand Landmarkerモデルをダウンロードします。既存環境を更新する場合は `README_スコアと難易度.txt` の差し替え手順を参照してください。

## ゲームルール

- **左右移動**：Webカメラに映した手を左右に動かす
- **生存点**：1秒生存するごとにレベルに応じた点数
- **回避点**：`10 × レベル × コンボ倍率`
- **コンボ倍率**：4回連続回避で2倍、8回で3倍、12回で最大4倍。被弾でリセット
- **黄色い星**：`40 × レベル` 点
- **水色のS**：12秒間有効、衝突を一度だけ防ぐシールド
- **難易度**：EASYは5ライフ・25秒ごとにレベルアップ、NORMALは3ライフ・20秒、HARDは2ライフ・16秒
- **一時停止**：手が検出されない間はタイマーごと停止
- **再開**：ゲームオーバー後、手を中央に1.5秒置く
- **終了**：`Q` または `Esc`

レベルアップすると障害物の頻度と落下速度が上がります。ハイスコアは難易度別に `webcam-game/highscores.json` にローカル保存されます。カメラ映像は保存・送信しません。

## 構成

- `main.py`：カメラ・MediaPipe・描画・ハイスコア保存
- `game_logic.py`：Python標準ライブラリだけで動作するゲームルール
- `download_model.py`：Google公式モデル取得
- `tests/test_game_logic.py`：ルール・画面生成・保存処理のテスト

## 実行例

```powershell
.\.venv-existing\Scripts\python.exe main.py --camera 0 --difficulty normal
.\.venv-existing\Scripts\python.exe main.py --camera 0 --difficulty easy
.\.venv-existing\Scripts\python.exe main.py --camera 0 --difficulty hard
.\.venv-existing\Scripts\python.exe main.py --snapshot examples/game-preview.png
```

## テスト

```powershell
.\.venv-existing\Scripts\python.exe -m pip install pytest
.\.venv-existing\Scripts\python.exe -m pytest -q tests
```

ゲームロジック・スコア保存・プレビュー描画の自動テストを実施。Webカメラの実動作とゲームの体感難易度はプレイヤーPCで最終確認してください。
