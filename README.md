# 2値BMP マルチクラス集計ツール

このツールは、複数枚の画像（主に領域抽出された二値画像など）を読み込み、K-Means法や重なり領域、白ピクセル率などのロジックを用いて自動的に複数クラスに分類するGUIアプリケーションです。
分類結果は、視覚的に分かりやすいツリーダイアグラム（組織図形式）として表示され、最終的な振り分け結果をExcel形式で出力可能です。

## インストールと起動方法

1. 必要なPythonパッケージをインストールします。
```bash
pip install -r requirements.txt
```

2. アプリケーションを起動します。
```bash
python main.py
```

## アーキテクチャ (ディレクトリ構成)
本アプリケーションは保守性を高めるため、以下のモジュール構成を採用しています。

- `main.py`: アプリケーションの起動用スクリプト
- `src/core/`: ビジネスロジック
  - `state.py`: （AppState）画像リストやクラス分類状態などのアプリケーションデータ
  - `classifier.py`: （ImageClassifier）クラスタリングアルゴリズムや画像オーバーレイ合成処理
  - `plugin_manager.py`: 外部プラグインの動的読み込みと実行管理
- `src/ui/`: ユーザーインターフェース
  - `main_window.py`: メインのTkinterウィンドウとUIイベント制御
  - `tree_renderer.py`: ツリーダイアグラムの専用描画クラス
  - `dialogs.py`: 自動分類などの設定用サブダイアログ
  - `constants.py`: UI全体で使用するカラーコードやサイズなどの定数
- `src/utils/`: 共通ユーティリティ
  - `logger.py`: 問題発生時の追跡を容易にする標準ロガー
  - `image_utils.py`: `white_ratio`などの画像処理に関する独立したヘルパー関数
- `plugins/`: 自動分類用のプラグインスクリプトを配置するフォルダ

## プラグインの追加方法

独自の分類ロジックを後から追加できます。`plugins/` フォルダにPythonスクリプトを配置するだけで、UIの「自動分類」ダイアログに選択肢として表示されます。

### プラグインの書き方

1. `plugins/` フォルダ内に `.py` ファイルを作成します（例: `白の面積で分ける.py`）。
2. ファイル内に `classify` という名前の関数を定義します。

```python
from PIL import Image
from typing import List, Any

def classify(images: List[Image.Image], state: Any, k: int) -> List[int]:
    """
    Args:
        images: 分類対象のPIL画像のリスト
        state: AppStateインスタンス（アプリの状態情報）
        k: 分割したいクラス数
    Returns:
        各画像の所属するクラスインデックス（0 ~ k-1）のリスト
    """
    labels = []
    for img in images:
        # ここに分類ロジックを記述
        labels.append(0)  # 例: 全部クラス0に入れる
    return labels
```

3. アプリを起動し「自動分類」ボタンを押すと、`🧩 [プラグイン] 白の面積で分ける` のように選択肢に追加されます。
