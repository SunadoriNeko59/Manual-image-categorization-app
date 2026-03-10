import tkinter as tk
from tkinter import filedialog
from typing import Callable, List, Optional
from ..core.state import AppState
from ..core.plugin_manager import PluginManager

class AutoClassifyDialog:
    """自動分類設定を行うためのダイアログ（モーダルウィンドウ）クラス。
    
    ユーザーから分類ターゲット、クラスタリング手法、クラス数(K)を受け取り、
    完了時にコールバック関数に渡して実行します。
    """
    # マスク画像の最大数
    MAX_MASKS = 5

    def __init__(self, parent: tk.Tk | tk.Toplevel, state: AppState, on_submit_callback: Callable):
        """
        Args:
            parent: 親ウィンドウ
            state: アプリケーションの状態データ
            on_submit_callback: [k, method, target, mask_paths]を受け取るコールバック関数
        """
        self.dlg = tk.Toplevel(parent)
        self.dlg.title("自動分類の設定")
        self.dlg.grab_set()  # 他の画面を操作できなくするモーダル制御
        self.dlg.resizable(False, False)
        self.state = state
        self.on_submit = on_submit_callback
        
        self.plugin_manager = PluginManager()

        # ターゲットの選択
        tk.Label(self.dlg, text="対象", font=("Arial", 10, "bold")).pack(pady=(10, 5))
        self.target_var = tk.StringVar(value="all")
        tk.Radiobutton(self.dlg, text="すべての画像（リセットして再分類）", variable=self.target_var, value="all").pack(anchor="w", padx=20)
        
        # 既存クラスがある場合は特定クラス内の再分類を選択可能にする
        if self.state.num_classes > 0:
            for c in range(self.state.num_classes):
                c_name, cnt = self.state.class_names[c].get(), self.state.class_counts[c]
                tk.Radiobutton(self.dlg, text=f"「{c_name}」の画像のみ ({cnt}枚)", variable=self.target_var, value=str(c)).pack(anchor="w", padx=20)

        # 手法の選択
        tk.Label(self.dlg, text="分類手法", font=("Arial", 10, "bold")).pack(pady=(10, 5))
        self.method_var = tk.StringVar(value="kmeans")
        self.method_var.trace_add("write", lambda *_: self._on_method_change())
        methods = [
            ("K-Means (全体の見た目の類似度)", "kmeans"),
            ("重なり領域ベース (位置依存・ホットスポット)", "overlap"),
            ("白率の範囲 (均等に分割)", "whiteratio"),
            ("白率0%とそれ以外", "whiteratio_zero"),
            ("白が外周に触れていない/触れている", "border_white"),
            ("マスク画像判定 (白領域の重なり)", "mask"),
        ]
        
        plugin_names = self.plugin_manager.get_plugin_names()
        for p_name in plugin_names:
            methods.append((f"🧩 [プラグイン] {p_name}", f"plugin:{p_name}"))
            
        for text, val in methods:
            tk.Radiobutton(self.dlg, text=text, variable=self.method_var, value=val).pack(anchor="w", padx=20)

        # クラス数 (K) の設定
        tk.Label(self.dlg, text="クラス数 (K):").pack(anchor="w", padx=20, pady=(10, 0))
        self.k_var = tk.IntVar(value=3)
        tk.Spinbox(self.dlg, from_=2, to=20, textvariable=self.k_var, width=5).pack(anchor="w", padx=20)

        # 膨張率の設定 (重なり領域ベース用)
        tk.Label(self.dlg, text="膨張率(%) [重なり領域ベース用]:").pack(anchor="w", padx=20, pady=(10, 0))
        self.dilation_var = tk.DoubleVar(value=self.state.overlap_dilation_pct.get())
        tk.Spinbox(self.dlg, from_=0.1, to=20.0, increment=0.1, format="%.1f", textvariable=self.dilation_var, width=5).pack(anchor="w", padx=20)

        # マスク画像選択フレーム（初期は非表示）
        self.mask_frame = tk.LabelFrame(self.dlg, text="マスク画像の選択 (最大5枚)", padx=10, pady=5)
        self.mask_path_vars: List[tk.StringVar] = []
        self.mask_entries: List[tk.Entry] = []
        
        for i in range(self.MAX_MASKS):
            row = tk.Frame(self.mask_frame)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=f"マスク {i+1}:", width=8, anchor="w").pack(side="left")
            sv = tk.StringVar(value="")
            entry = tk.Entry(row, textvariable=sv, width=35)
            entry.pack(side="left", padx=(0, 5), fill="x", expand=True)
            tk.Button(row, text="参照", width=4, command=lambda idx=i: self._browse_mask(idx)).pack(side="left")
            self.mask_path_vars.append(sv)
            self.mask_entries.append(entry)

        # ボタン
        btn_frame = tk.Frame(self.dlg)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="実行", width=10, command=self._submit).pack(side="left", padx=5)
        tk.Button(btn_frame, text="キャンセル", width=10, command=self.dlg.destroy).pack(side="left", padx=5)

    def _on_method_change(self) -> None:
        """分類手法が変更されたとき、マスク選択UIの表示/非表示を切り替えます。"""
        if self.method_var.get() == "mask":
            self.mask_frame.pack(anchor="w", padx=20, pady=(10, 5), fill="x")
        else:
            self.mask_frame.pack_forget()

    def _browse_mask(self, idx: int) -> None:
        """マスク画像の参照ボタンが押されたとき、ファイル選択ダイアログを表示します。"""
        path = filedialog.askopenfilename(
            title=f"マスク画像 {idx+1} を選択",
            filetypes=[("画像ファイル", "*.bmp *.png *.jpg *.jpeg *.tif *.tiff"), ("すべてのファイル", "*.*")]
        )
        if path:
            self.mask_path_vars[idx].set(path)

    def _submit(self) -> None:
        """実行ボタン押下時の処理。ダイアログを閉じ、コールバックを呼ぶ。"""
        k = self.k_var.get()
        method = self.method_var.get()
        target = self.target_var.get()
        if hasattr(self, 'dilation_var'):
            self.state.overlap_dilation_pct.set(self.dilation_var.get())
        
        # マスク画像のパスを収集（空でないもののみ）
        mask_paths = [sv.get() for sv in self.mask_path_vars if sv.get().strip()]
        
        self.dlg.destroy()
        self.on_submit(k, method, target, mask_paths)
