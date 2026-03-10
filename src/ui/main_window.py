import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, colorchooser

from PIL import Image, ImageTk, ImageGrab
from openpyxl import Workbook
from typing import Optional, List

from ..core.state import AppState
from ..core.classifier import ImageClassifier
from ..core.plugin_manager import PluginManager
from ..utils.logger import logger
from ..utils.image_utils import white_ratio
from .constants import THUMB_SIZE, CLASS_COLORS
from .tree_renderer import TreeRenderer
from .dialogs import AutoClassifyDialog

class ImageMultiClassApp:
    """アプリケーションのメインウィンドウと、ユーザー操作に応じた全体制御を行うクラス。"""
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("2値BMP マルチクラス集計（リファクタリング版）")
        
        # 状態データとロガーの初期化
        self.state = AppState()
        self.state.alpha = tk.IntVar(value=128)
        
        self.class_tabs = []    # [(tab_frame, canvas, inner_frame), ...]
        
        logger.info("UIの構築を開始します")
        self._build_ui()
        self.tree_renderer = TreeRenderer(self.sankey_canvas, self.state)
        logger.info("アプリケーションの初期化が完了しました")

    def _build_ui(self) -> None:
        # --- Top Menu ---
        top = tk.Frame(self.root)
        top.pack(fill="x")
        tk.Button(top, text="フォルダ選択", command=self.load_folder).pack(side="left", padx=5)
        tk.Button(top, text="+ クラス追加", command=self.add_class).pack(side="left", padx=5)
        tk.Button(top, text="Excel保存", command=self.save_excel).pack(side="left", padx=5)
        tk.Button(top, text="グラフ保存", command=self.save_tree_image).pack(side="left", padx=5)
        tk.Button(top, text="自動分類", command=self.open_auto_classify_dialog).pack(side="left", padx=5)
        self.undo_btn = tk.Button(top, text="⏮ 1つ前に戻る", state="disabled", command=self.undo_classification)
        self.undo_btn.pack(side="left", padx=5)
        self.reclassify_btn = tk.Button(top, text="白率で再分類", command=self.reclassify_by_white_ratio)
        self.count_label = tk.Label(top)
        self.count_label.pack(side="right", padx=10)

        # --- Main Layout (Resizable Panes) ---
        main = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main.pack(fill="both", expand=True, padx=5, pady=5)

        # Left Pane (Notebook)
        left_pane = tk.Frame(main)
        main.add(left_pane, weight=1)  # Expandable
        
        self.notebook = ttk.Notebook(left_pane)
        self.notebook.pack(fill="both", expand=True)
        self.tab_all, _, self.frame_all = self._create_scrollable_tab("すべて (All)")
        self.tab_unclassified, _, self.frame_unclassified = self._create_scrollable_tab("未分類")

        # Right Pane (Settings and Graph Canvas)
        right = tk.Frame(main)
        # 初期幅を持たせつつ、ドラッグでサイズ変更可能にする (pack_propagate(False)は削除)
        main.add(right, weight=1)

# 表示形式の選択肢はツリーのみのため削除

        tk.Label(right, text="クラス設定", font=("Arial", 10, "bold")).pack(anchor="w", pady=(10, 0))
        self.class_name_frame = tk.Frame(right)
        self.class_name_frame.pack(anchor="w", fill="x", pady=2)

        tk.Label(right, text="赤の透明度").pack(anchor="w")
        tk.Scale(right, from_=0, to=255, orient="horizontal", variable=self.state.alpha, command=lambda e: self._on_alpha_change()).pack(fill="x")

        # キャンバスにスクロールバーを追加
        canvas_frame = tk.Frame(right)
        canvas_frame.pack(fill="both", expand=True, pady=5)
        
        self.sankey_canvas = tk.Canvas(canvas_frame, bg="white", highlightthickness=1, highlightbackground="#CCC", height=300)
        
        vbar = tk.Scrollbar(canvas_frame, orient="vertical", command=self.sankey_canvas.yview)
        hbar = tk.Scrollbar(canvas_frame, orient="horizontal", command=self.sankey_canvas.xview)
        
        self.sankey_canvas.configure(yscrollcommand=vbar.set, xscrollcommand=hbar.set)
        
        vbar.pack(side="right", fill="y")
        hbar.pack(side="bottom", fill="x")
        self.sankey_canvas.pack(side="left", fill="both", expand=True)
        
        # マウスホイールでスクロールできるようにバインド
        self.sankey_canvas.bind("<MouseWheel>", self._on_canvas_mousewheel)
        self.sankey_canvas.bind("<Shift-MouseWheel>", self._on_canvas_shift_mousewheel)

    def _on_canvas_mousewheel(self, event):
        self.sankey_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_canvas_shift_mousewheel(self, event):
        self.sankey_canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")

    def _create_scrollable_tab(self, title: str):
        tab = tk.Frame(self.notebook)
        self.notebook.add(tab, text=title)
        canvas = tk.Canvas(tab, width=420)
        sb = tk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="left", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        inner_frame = tk.Frame(canvas)
        canvas.create_window((0, 0), window=inner_frame, anchor="nw")
        inner_frame.bind("<Configure>", lambda e, c=canvas: c.configure(scrollregion=c.bbox("all")))
        canvas.bind_all("<MouseWheel>", lambda event, c=canvas: c.yview_scroll(int(-event.delta / 120), "units") if str(c.winfo_class()) == "Canvas" else None)
        return tab, canvas, inner_frame

    def _on_alpha_change(self) -> None:
        ImageClassifier.rebuild_all_overlays(self.state)
        self.tree_renderer.draw()

    # --- Folder & Class Management ---
    def load_folder(self) -> None:
        folder = filedialog.askdirectory()
        if not folder: return
        logger.info(f"フォルダを読み込みます: {folder}")
        
        n = 2
        self._clear_ui_and_state()
        for i in range(n):
            self._create_class(f"Class {i+1}")

        files = [f for f in os.listdir(folder) if f.lower().endswith(('.jpg', '.png', '.bmp'))]
        for idx, fname in enumerate(files):
            img = Image.open(os.path.join(folder, fname))
            self.state.images.append(img)
            self.state.filenames.append(fname)
            ratio = white_ratio(img)
            self.state.white_ratios.append(ratio)

            thumb = img.copy()
            thumb.thumbnail(THUMB_SIZE)
            tk_thumb = ImageTk.PhotoImage(thumb)
            self.state.thumbs.append(tk_thumb)

            vars_per_image = [tk.BooleanVar() for _ in range(self.state.num_classes)]
            self.state.class_vars.append(vars_per_image)

            frame = tk.Frame(self.frame_all, relief="ridge", borderwidth=1)
            frame.grid(row=idx // 3, column=idx % 3, padx=5, pady=5)
            tk.Label(frame, image=tk_thumb).pack()
            frame.image = tk_thumb
            tk.Label(frame, text=f"白率: {ratio:.1%}").pack()

            for c in range(self.state.num_classes):
                self._create_checkbutton(frame, idx, c)

        self.tree_renderer.draw()
        self.update_class_tabs()
        self.count_label.config(text=f"画像数: {len(self.state.images)} / チェック総数: 0")
        logger.info(f"{len(self.state.images)}枚の画像を読み込みました")

    def _clear_ui_and_state(self) -> None:
        for w in self.frame_all.winfo_children(): w.destroy()
        for tab_tuple in self.class_tabs: self.notebook.forget(tab_tuple[0])
        self.class_tabs.clear()
        for w in self.class_name_frame.winfo_children(): w.destroy()
        self.sankey_canvas.delete("all")
        self.state.clear_project()

    def _on_color_click(self, class_idx: int, label_widget: tk.Label) -> None:
        current_color = self.state.class_colors_used[class_idx]
        color_tuple = colorchooser.askcolor(initialcolor=current_color, title=f"{self.state.class_names[class_idx].get()} の色を選択")
        if color_tuple and color_tuple[1]:
            new_color = color_tuple[1]
            self.state.class_colors_used[class_idx] = new_color
            label_widget.config(bg=new_color)
            self.tree_renderer.draw()

    def _create_class(self, name: str) -> None:
        name_var = tk.StringVar(value=name)
        name_var.trace_add("write", lambda *args: self._on_class_name_changed())
        idx = self.state.num_classes
        
        self.state.class_names.append(name_var)
        self.state.class_counts.append(0)
        self.state.class_overlays.append(None)
        
        color = CLASS_COLORS[idx % len(CLASS_COLORS)]
        self.state.class_colors_used.append(color)
        self.state.class_ranges.append((tk.DoubleVar(value=0 if idx==0 else idx*10), tk.DoubleVar(value=100 if idx>=9 else (idx+1)*10)))
        
        self.state.num_classes += 1

        row = tk.Frame(self.class_name_frame)
        row.pack(anchor="w", fill="x", pady=1)
        lbl = tk.Label(row, text="  ", bg=color, width=2, relief="solid", cursor="hand2")
        lbl.pack(side="left", padx=(0, 3))
        lbl.bind("<Button-1>", lambda e, i=idx, l=lbl: self._on_color_click(i, l))
        tk.Entry(row, textvariable=name_var, width=12).pack(side="left")
        
        rf = tk.Frame(row)
        tk.Entry(rf, textvariable=self.state.class_ranges[idx][0], width=4).pack(side="left")
        tk.Label(rf, text="%~").pack(side="left")
        tk.Entry(rf, textvariable=self.state.class_ranges[idx][1], width=4).pack(side="left")
        tk.Label(rf, text="%").pack(side="left")
        if self.state.whiteratio_mode: rf.pack(side="left")

    def add_class(self) -> None:
        if not self.state.images: return
        idx = self.state.num_classes
        self._create_class(f"Class {idx+1}")
        tab_tuple = self._create_scrollable_tab(self.state.class_names[idx].get())
        self.class_tabs.append(tab_tuple)

        for i, frame in enumerate(self.frame_all.winfo_children()):
            var = tk.BooleanVar()
            self.state.class_vars[i].append(var)
            self._create_checkbutton(frame, i, idx)
        self.tree_renderer.draw()

    def _create_checkbutton(self, parent_frame: tk.Frame, img_idx: int, c_idx: int) -> None:
        var = self.state.class_vars[img_idx][c_idx]
        tk.Checkbutton(parent_frame, textvariable=self.state.class_names[c_idx], variable=var,
                       command=lambda: self.on_check(img_idx, c_idx, var)).pack(anchor="w")

    def _on_class_name_changed(self) -> None:
        self.tree_renderer.draw()
        self.update_class_tabs()

    def on_check(self, img_idx: int, c_idx: int, var: tk.BooleanVar) -> None:
        self.state.class_counts[c_idx] += 1 if var.get() else -1
        ImageClassifier.rebuild_overlay(self.state, c_idx)
        self.tree_renderer.draw()
        self.update_class_tabs()
        self.count_label.config(text=f"画像数: {len(self.state.images)} / チェック総数: {sum(self.state.class_counts)}")

    # --- UI Sync ---
    def update_class_tabs(self) -> None:
        for w in self.frame_unclassified.winfo_children(): w.destroy()
        
        display_idx = 0
        for idx, vars_per_image in enumerate(self.state.class_vars):
            if not any(v.get() for v in vars_per_image):
                frame = tk.Frame(self.frame_unclassified, relief="ridge", borderwidth=1)
                frame.grid(row=display_idx // 3, column=display_idx % 3, padx=5, pady=5)
                tk.Label(frame, image=self.state.thumbs[idx]).pack()
                tk.Label(frame, text=f"白率: {self.state.white_ratios[idx]:.1%}").pack()
                for c in range(self.state.num_classes):
                    if c not in self.state.hidden_checkboxes:
                        self._create_checkbutton(frame, idx, c)
                display_idx += 1

        if len(self.class_tabs) != self.state.num_classes: return

        for c, (tab_frame, _, inner_frame) in enumerate(self.class_tabs):
            if c in self.state.hidden_checkboxes:
                try: self.notebook.hide(tab_frame)
                except tk.TclError: pass
                continue
            
            try: self.notebook.tab(tab_frame, text=self.state.class_names[c].get())
            except tk.TclError: pass
            
            for w in inner_frame.winfo_children(): w.destroy()
            d_idx = 0
            for idx, vars_per_image in enumerate(self.state.class_vars):
                if vars_per_image[c].get():
                    frame = tk.Frame(inner_frame, relief="ridge", borderwidth=1)
                    frame.grid(row=d_idx // 3, column=d_idx % 3, padx=5, pady=5)
                    tk.Label(frame, image=self.state.thumbs[idx]).pack()
                    tk.Label(frame, text=f"白率: {self.state.white_ratios[idx]:.1%}").pack()
                    self._create_checkbutton(frame, idx, c)
                    d_idx += 1

    # --- Undo ---
    def undo_classification(self) -> None:
        if not self.state.history: return
        h = self.state.history.pop()
        if not self.state.history: self.undo_btn.config(state="disabled")

        for tab_tuple in self.class_tabs:
            self.notebook.forget(tab_tuple[0])
            tab_tuple[0].destroy()
        self.class_tabs.clear()
        for w in self.class_name_frame.winfo_children(): w.destroy()
        self.sankey_canvas.delete("all")
        
        for frame in self.frame_all.winfo_children():
            for w in frame.winfo_children():
                if isinstance(w, tk.Checkbutton): w.destroy()

        self.state.clear_classes()
        self.state.classification_tree = h["classification_tree"]
        self.state.whiteratio_mode = h["whiteratio_mode"]
        if "graph_type" in h:
            self.state.graph_type.set(h["graph_type"])
        if "overlap_dilation_pct" in h:
            self.state.overlap_dilation_pct.set(h["overlap_dilation_pct"])
        self.state.hidden_checkboxes = h["hidden_checkboxes"]
        if self.state.whiteratio_mode: self.reclassify_btn.pack(side="left", padx=5)
        else: self.reclassify_btn.pack_forget()

        for i in range(h["num_classes"]):
            name = h["class_names"][i]
            self._create_class(name)
            self.class_tabs.append(self._create_scrollable_tab(name))
            if i < len(h["class_colors_used"]):
                self.state.class_colors_used[i] = h["class_colors_used"][i]
                for w in self.class_name_frame.winfo_children()[-1].winfo_children():
                    if isinstance(w, tk.Label) and w.cget("text") == "  ":
                        w.config(bg=h["class_colors_used"][i]); break
            if i < len(h["class_ranges"]):
                self.state.class_ranges[i][0].set(h["class_ranges"][i][0])
                self.state.class_ranges[i][1].set(h["class_ranges"][i][1])

        saved_vars = h["class_vars"]
        for idx, frame in enumerate(self.frame_all.winfo_children()):
            vp = [tk.BooleanVar() for _ in range(self.state.num_classes)]
            self.state.class_vars.append(vp)
            for c in range(self.state.num_classes):
                if idx < len(saved_vars) and c < len(saved_vars[idx]):
                    vp[c].set(saved_vars[idx][c])
                if c not in self.state.hidden_checkboxes:
                    self._create_checkbutton(frame, idx, c)

        for i in range(self.state.num_classes):
            self.state.class_counts[i] = sum(1 for vp in self.state.class_vars if vp[i].get())

        logger.info("Undo: 前の状態に復元しました")
        ImageClassifier.rebuild_all_overlays(self.state)
        self.tree_renderer.draw()
        self.update_class_tabs()

    # --- Tree Save ---
    def save_tree_image(self) -> None:
        if self.state.num_classes == 0 or not self.state.images:
            messagebox.showwarning("警告", "保存するデータがありません")
            return
            
        filepath = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("All Files", "*.*")],
            title="ツリーダイアグラムを保存"
        )
        if not filepath:
            return

        self.root.update_idletasks()
        x = self.sankey_canvas.winfo_rootx()
        y = self.sankey_canvas.winfo_rooty()
        w = self.sankey_canvas.winfo_width()
        h = self.sankey_canvas.winfo_height()

        try:
            try:
                import ctypes
                scale = ctypes.windll.shcore.GetScaleFactorForDevice(0) / 100.0
            except Exception:
                scale = 1.0

            bbox = (
                int(x * scale), 
                int(y * scale), 
                int((x + w) * scale), 
                int((y + h) * scale)
            )

            img = ImageGrab.grab(bbox=bbox)
            img.save(filepath)
            logger.info(f"ツリーダイアグラムを保存しました: {filepath}")
            messagebox.showinfo("保存完了", f"ツリーダイアグラムを保存しました\n{filepath}")
        except Exception as e:
            logger.error(f"ツリーダイアグラムの保存失敗: {e}")
            messagebox.showerror("エラー", f"画像の保存に失敗しました\n{e}")

    # --- Auto Classification Routing ---
    def open_auto_classify_dialog(self) -> None:
        if not self.state.images:
            messagebox.showwarning("警告", "画像が読み込まれていません")
            return
        AutoClassifyDialog(self.root, self.state, self._on_auto_classify_submit)

    def _on_auto_classify_submit(self, k: int, method: str, target: str, mask_paths: List[str] = None) -> None:
        if mask_paths is None:
            mask_paths = []

        if method in ("whiteratio_zero", "border_white"):
            k = 2
        
        # マスク手法の場合、クラス数はマスク数+1（No Match用）
        if method == "mask":
            if not mask_paths:
                messagebox.showwarning("警告", "マスク画像が選択されていません")
                return
            # マスク画像を読み込む
            mask_images = []
            for mp in mask_paths:
                try:
                    mask_images.append(Image.open(mp))
                except Exception as e:
                    messagebox.showerror("エラー", f"マスク画像の読み込みに失敗しました\n{mp}\n{e}")
                    return
            k = len(mask_images) + 1  # マスク数 + No Match

        self.state.save_state()
        self.undo_btn.config(state="normal")
        
        # プラグイン判定
        is_plugin = method.startswith("plugin:")
        plugin_name = method.split(":", 1)[1] if is_plugin else None

        if target == "all":
            prefix = plugin_name if is_plugin else ("Auto" if method not in ("whiteratio", "mask") else ("白率" if method == "whiteratio" else "Mask"))
            self._reset_classes(k, prefix=prefix)
            if is_plugin:
                try:
                    pm = PluginManager()
                    labels = pm.execute_plugin(plugin_name, self.state.images, self.state, k)
                    self._apply_labels(labels, k)
                except Exception as e:
                    logger.error(f"プラグイン実行エラー: {e}")
                    messagebox.showerror("エラー", f"プラグインの実行に失敗しました\n{e}")
                    return
            elif method == "kmeans":
                labels = ImageClassifier.kmeans_cluster(self.state.images, k)
                self._apply_labels(labels, k)
            elif method == "overlap":
                labels = ImageClassifier.overlap_cluster(self.state.images, k, dilation_pct=self.state.overlap_dilation_pct.get())
                if labels is None: 
                    messagebox.showwarning("警告", "重なり領域が検出できませんでした")
                    return
                self._apply_labels(labels, k)
            elif method == "whiteratio":
                self.state.whiteratio_mode = True
                self.reclassify_btn.pack(side="left", padx=5)
                step = 100.0 / k
                for i in range(k):
                    self.state.class_ranges[i][0].set(round(i*step, 1))
                    self.state.class_ranges[i][1].set(round((i+1)*step, 1))
                    self.state.class_names[i].set(f"{i*step:.0f}%〜{(i+1)*step:.0f}%")
                self.reclassify_by_white_ratio()
                self._build_tree(k)
            elif method == "whiteratio_zero":
                labels = ImageClassifier.whiteratio_zero_cluster(self.state.white_ratios)
                self.state.class_names[0].set("白率 0%")
                self.state.class_names[1].set("白率 0%超")
                self._apply_labels(labels, k)
            elif method == "border_white":
                labels = ImageClassifier.border_white_cluster(self.state.images)
                self.state.class_names[0].set("外周に白なし")
                self.state.class_names[1].set("外周に白あり")
                self._apply_labels(labels, k)
            elif method == "mask":
                labels = ImageClassifier.mask_cluster(self.state.images, mask_images)
                for mi, mp in enumerate(mask_paths):
                    basename = os.path.splitext(os.path.basename(mp))[0]
                    self.state.class_names[mi].set(basename)
                    self.state.mask_overlays[mi] = mask_images[mi]
                self.state.class_names[len(mask_paths)].set("No Match")
                self._apply_labels(labels, k)
        else:
            t_class = int(target)
            t_indices = [i for i, vp in enumerate(self.state.class_vars) if vp[t_class].get()]
            s_name = self.state.class_names[t_class].get()
            t_images = [self.state.images[i] for i in t_indices]

            if is_plugin:
                try:
                    pm = PluginManager()
                    labels = pm.execute_plugin(plugin_name, t_images, self.state, k)
                except Exception as e:
                    logger.error(f"プラグイン実行エラー: {e}")
                    messagebox.showerror("エラー", f"プラグインの実行に失敗しました\n{e}")
                    return
            elif method == "kmeans": labels = ImageClassifier.kmeans_cluster(t_images, k)
            elif method == "overlap": labels = ImageClassifier.overlap_cluster(t_images, k, dilation_pct=self.state.overlap_dilation_pct.get())
            elif method == "whiteratio": labels = ImageClassifier.whiteratio_cluster([self.state.white_ratios[i] for i in t_indices], k)
            elif method == "whiteratio_zero":
                labels = ImageClassifier.whiteratio_zero_cluster([self.state.white_ratios[i] for i in t_indices])
            elif method == "border_white":
                labels = ImageClassifier.border_white_cluster(t_images)
            elif method == "mask":
                labels = ImageClassifier.mask_cluster(t_images, mask_images)
            
            if labels is not None:
                self._sub_classify_apply(labels, k, t_indices, t_class, s_name)
                
                if method == "whiteratio_zero":
                    new_idx = self.state.num_classes - 2
                    self.state.class_names[new_idx].set(f"{s_name}_白率0%")
                    self.state.class_names[new_idx + 1].set(f"{s_name}_0%超")
                    self.update_class_tabs()
                elif method == "border_white":
                    new_idx = self.state.num_classes - 2
                    self.state.class_names[new_idx].set(f"{s_name}_外白なし")
                    self.state.class_names[new_idx + 1].set(f"{s_name}_外白あり")
                    self.update_class_tabs()
                elif method == "mask":
                    # マスクファイル名をサブクラス名に設定
                    new_start = self.state.num_classes - k
                    for mi, mp in enumerate(mask_paths):
                        basename = os.path.splitext(os.path.basename(mp))[0]
                        self.state.class_names[new_start + mi].set(f"{s_name}_{basename}")
                        # マスク画像をオーバーレイ用に保存
                        self.state.mask_overlays[new_start + mi] = mask_images[mi]
                    self.state.class_names[new_start + len(mask_paths)].set(f"{s_name}_NoMatch")
                    self.update_class_tabs()

    def _reset_classes(self, k: int, prefix: str) -> None:
        for tab_tuple in self.class_tabs: self.notebook.forget(tab_tuple[0])
        self.class_tabs.clear()
        for w in self.class_name_frame.winfo_children(): w.destroy()
        
        self.state.clear_classes()
        self.reclassify_btn.pack_forget()

        for i in range(k):
            name = f"{prefix} {i+1}"
            self._create_class(name)
            self.class_tabs.append(self._create_scrollable_tab(name))

        for idx, frame in enumerate(self.frame_all.winfo_children()):
            for w in frame.winfo_children():
                if isinstance(w, tk.Checkbutton): w.destroy()
            vp = [tk.BooleanVar() for _ in range(k)]
            self.state.class_vars.append(vp)
            for c in range(k): self._create_checkbutton(frame, idx, c)

    def _apply_labels(self, labels: list[int], k: int) -> None:
        for idx, label in enumerate(labels):
            self.state.class_vars[idx][label].set(True)
            self.state.class_counts[label] += 1
        self._build_tree(k)
        ImageClassifier.rebuild_all_overlays(self.state)
        self.tree_renderer.draw()
        self.update_class_tabs()

    def _build_tree(self, k: int) -> None:
        self.state.classification_tree = {"name": "全体", "class_idx": None, "children": []}
        for i in range(k):
            self.state.classification_tree["children"].append({
                "name": self.state.class_names[i].get(), "class_idx": i, "count": self.state.class_counts[i], "children": []
            })

    def _sub_classify_apply(self, labels: list[int], k: int, target_indices: list[int], target_class: int, source_class_name: str) -> None:
        self.reclassify_btn.pack_forget()
        self.state.whiteratio_mode = False
        
        for idx in target_indices: self.state.class_vars[idx][target_class].set(False)
        self.state.class_counts[target_class] = sum(1 for vp in self.state.class_vars if vp[target_class].get())

        new_start = self.state.num_classes
        for i in range(k):
            sub_name = f"{source_class_name}_{i+1}"
            self._create_class(sub_name)
            self.class_tabs.append(self._create_scrollable_tab(sub_name))
            for vp in self.state.class_vars:
                while len(vp) < self.state.num_classes: vp.append(tk.BooleanVar())

        self.state.hidden_checkboxes.add(target_class)

        for idx, frame in enumerate(self.frame_all.winfo_children()):
            for w in frame.winfo_children():
                if isinstance(w, tk.Checkbutton): w.destroy()
            for c in range(self.state.num_classes):
                if c not in self.state.hidden_checkboxes:
                    self._create_checkbutton(frame, idx, c)

        for li, label in enumerate(labels):
            new_c = new_start + label
            self.state.class_vars[target_indices[li]][new_c].set(True)
            self.state.class_counts[new_c] += 1

        if self.state.classification_tree:
            parent_node = self._find_tree_node(self.state.classification_tree, target_class)
            if parent_node:
                parent_node["children"] = []
                for i in range(k):
                    c_idx = new_start + i
                    parent_node["children"].append({"name": self.state.class_names[c_idx].get(), "class_idx": c_idx, "count": self.state.class_counts[c_idx], "children": []})
                parent_node["count"] = self.state.class_counts[target_class]

        ImageClassifier.rebuild_all_overlays(self.state)
        self.tree_renderer.draw()
        self.update_class_tabs()

    def _find_tree_node(self, node: dict, class_idx: int) -> Optional[dict]:
        if node.get("class_idx") == class_idx: return node
        for child in node.get("children", []):
            found = self._find_tree_node(child, class_idx)
            if found: return found
        return None

    def reclassify_by_white_ratio(self) -> None:
        if not self.state.images: return
        self.state.save_state()
        self.undo_btn.config(state="normal")
        
        for idx, (vp, ratio) in enumerate(zip(self.state.class_vars, self.state.white_ratios)):
            for v in vp: v.set(False)
            ratio_pct = ratio * 100
            for c, (min_var, max_var) in enumerate(self.state.class_ranges):
                if min_var.get() <= ratio_pct <= max_var.get():
                    vp[c].set(True); break
        
        for i in range(self.state.num_classes): self.state.class_counts[i] = 0
        for vp in self.state.class_vars:
            for c, v in enumerate(vp):
                if v.get(): self.state.class_counts[c] += 1

        ImageClassifier.rebuild_all_overlays(self.state)
        self.tree_renderer.draw()
        self.update_class_tabs()

    def save_excel(self) -> None:
        if not self.state.images: return
        path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")])
        if not path: return
        
        wb = Workbook()
        ws = wb.active
        ws.append(["filename"] + [n.get() for n in self.state.class_names])
        for fname, vp in zip(self.state.filenames, self.state.class_vars):
            ws.append([fname] + [1 if v.get() else 0 for v in vp])
        wb.save(path)
        logger.info(f"分類結果をExcelに保存しました: {path}")
        messagebox.showinfo("保存完了", "Excelに保存しました")
