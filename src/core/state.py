import tkinter as tk
from typing import List, Tuple, Dict, Any, Optional, Set
from PIL import Image, ImageTk

class AppState:
    """アプリケーション全体の状態（データ）を保持・管理するクラス。
    
    画像データ、分類結果、サンキーダイアグラムのノード情報、UI用変数などを一元管理します。
    すべてのUIコンポーネントやロジックは、この状態クラスを参照・更新することで同期を保ちます。
    """
    def __init__(self):
        # 画像関連の基本データ
        self.images: List[Image.Image] = []       # PIL.Image のリスト (オリジナル画像)
        self.filenames: List[str] = []            # ファイル名のリスト
        self.white_ratios: List[float] = []       # 各画像の白ピクセル割合(0.0~1.0)
        self.thumbs: List[ImageTk.PhotoImage] = [] # Tkinter UI表示用サムネイル画像の参照
        self.overlay_tks: List[ImageTk.PhotoImage] = [] # サンキーダイアグラム用オーバーレイ画像の参照

        # クラス分類に関連するデータ
        self.num_classes: int = 0
        self.class_names: List[tk.StringVar] = [] # 各クラスの名前
        self.class_counts: List[int] = []         # 各クラスに属する画像の枚数
        self.class_overlays: List[Optional[Image.Image]] = [] # 各クラスの合成オーバーレイ画像(PIL)
        self.class_colors_used: List[str] = []    # 各クラスに割り当てられた表示色(Hex)
        self.class_ranges: List[Tuple[tk.DoubleVar, tk.DoubleVar]] = [] # 白率分類用の(最小値, 最大値)のUI変数

        # チェックボックスの状態
        # 2次元配列: [image_index][class_index] -> tk.BooleanVar
        # 各画像がどのクラスに属しているかを保持します
        self.class_vars: List[List[tk.BooleanVar]] = []

        # サンキーダイアグラム表示用の階層構造データ
        self.classification_tree: Optional[Dict[str, Any]] = None
        
        # Undo（元に戻す）機能用の履歴
        self.history: List[Dict[str, Any]] = []
        
        # UI上で非表示（分類済みなど）になっているチェックボックス/クラスのインデックス
        self.hidden_checkboxes: Set[int] = set()
        
        # マスク画像判定用：クラスインデックス → マスクPIL画像の対応
        self.mask_overlays: Dict[int, Image.Image] = {}
        
        # 全体設定
        self.alpha: Optional[tk.IntVar] = None # オーバーレイ赤色の透明度(0-255)
        self.whiteratio_mode: bool = False     # 現在白率ベースの分類モードかどうか
        self.current_whiteratio_target: Optional[Any] = None # 白率再分類の対象（"all" または ("sub", t_indices, range)）
        self.graph_type: tk.StringVar = tk.StringVar(value="tree") # "tree" のみ
        self.overlap_dilation_pct: tk.DoubleVar = tk.DoubleVar(value=1.0) # 重なり領域ベースの膨張率(%)

    def clear_project(self) -> None:
        """プロジェクト全体を初期状態にリセットします。"""
        self.images.clear()
        self.filenames.clear()
        self.white_ratios.clear()
        self.thumbs.clear()
        self.overlay_tks.clear()
        self.clear_classes()

    def clear_classes(self) -> None:
        """クラス分類とそれに関連する変数を初期状態にリセットします。"""
        self.num_classes = 0
        self.class_names.clear()
        self.class_counts.clear()
        self.class_overlays.clear()
        self.class_colors_used.clear()
        self.class_ranges.clear()
        self.class_vars.clear()
        self.classification_tree = None
        self.hidden_checkboxes.clear()
        self.mask_overlays.clear()
        self.current_whiteratio_target = None
        
        # graph_type と alpha, whiteratio_mode は基本的にリセット後も引き継ぐ想定

    def save_state(self) -> None:
        """現在のクラス分類状態を履歴オブジェクトに保存（スナップショット）します。
        
        最大10個前までの状態を保持し、Undo機能を提供します。
        """
        import copy
        state = {
            "num_classes": self.num_classes,
            "class_names": [n.get() for n in self.class_names],
            "class_colors_used": list(self.class_colors_used),
            "class_ranges": [(r[0].get(), r[1].get()) for r in self.class_ranges],
            "class_vars": [[v.get() for v in vp] for vp in self.class_vars],
            "classification_tree": copy.deepcopy(self.classification_tree),
            "whiteratio_mode": self.whiteratio_mode,
            "current_whiteratio_target": copy.deepcopy(self.current_whiteratio_target),
            "graph_type": self.graph_type.get(),
            "overlap_dilation_pct": self.overlap_dilation_pct.get(),
            "hidden_checkboxes": set(self.hidden_checkboxes)
        }
        self.history.append(state)
        # 履歴件数の上限を10個までに制限
        if len(self.history) > 10:
            self.history.pop(0)
