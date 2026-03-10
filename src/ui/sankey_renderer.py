import tkinter as tk
from PIL import Image, ImageTk
from typing import List, Tuple, Dict, Any, Optional

from ..core.state import AppState
from .constants import OVERLAY_THUMB

class SankeyRenderer:
    """サンキーダイアグラムを描画する専用のレンダラークラス。
    
    キャンバスとAppStateを受け取り、現在の分類結果（クラスカウントや階層構造）を視覚化します。
    """
    def __init__(self, canvas: tk.Canvas, state: AppState):
        self.canvas = canvas
        self.state = state

    def draw(self) -> None:
        """キャンバスをクリアし、現在の状態に基づいてサンキーダイアグラムを再描画します。"""
        self.canvas.delete("all")
        # 描画のたびにオーバーレイのTkinter画像参照をクリア
        self.state.overlay_tks = []

        if self.state.num_classes == 0 or not self.state.images:
            return

        self.canvas.update_idletasks()
        cw = self.canvas.winfo_width() or 360
        ch = self.canvas.winfo_height() or 300

        total = len(self.state.images)
        classified = sum(self.state.class_counts)
        unclassified = max(total - classified, 0)

        margin_top = 25
        margin_bottom = 10
        usable_h = ch - margin_top - margin_bottom
        node_w = 16
        overlay_size = OVERLAY_THUMB

        tree = self.state.classification_tree
        if tree and tree.get("children"):
            self._update_tree_counts(tree)
            self._update_tree_names(tree)
            depth = self._tree_depth(tree)
            has_leaves_at_depth2 = depth > 2
        else:
            has_leaves_at_depth2 = False

        gtype = self.state.graph_type.get()
        if gtype == "tree":
            self._draw_tree(cw, ch, usable_h, margin_top, node_w, overlay_size, total, unclassified, depth if tree else 1, tree)
        elif gtype == "bar":
            self._draw_stacked_bar(cw, ch, usable_h, margin_top, overlay_size, total, unclassified, depth if tree else 1, tree)
        else:
            if tree and has_leaves_at_depth2:
                self._draw_recursive_multilayer(tree, cw, ch, usable_h, margin_top, node_w, overlay_size, total, unclassified, depth)
            else:
                self._draw_singlelayer(cw, ch, usable_h, margin_top, node_w, overlay_size, total, unclassified)

        # 描画された要素全体を囲むようにスクロール領域を更新
        bbox = self.canvas.bbox("all")
        if bbox:
            # 少しマージンを持たせる (左, 上, 右, 下)
            self.canvas.config(scrollregion=(min(0, bbox[0] - 20), min(0, bbox[1] - 20), bbox[2] + 20, bbox[3] + 20))
        else:
            self.canvas.config(scrollregion=(0, 0, cw, ch))

    def _update_tree_counts(self, node: Dict[str, Any]) -> None:
        idx = node.get("class_idx")
        base_count = 0
        if idx is not None and idx < len(self.state.class_counts):
            base_count = self.state.class_counts[idx]
        
        children_sum = 0
        for child in node.get("children", []):
            self._update_tree_counts(child)
            children_sum += child.get("count", 0)
            
        node["count"] = base_count + children_sum

    def _update_tree_names(self, node: Dict[str, Any]) -> None:
        idx = node.get("class_idx")
        if idx is not None and idx < len(self.state.class_names):
            node["name"] = self.state.class_names[idx].get()
        for child in node.get("children", []):
            self._update_tree_names(child)

    def _tree_depth(self, node: Dict[str, Any]) -> int:
        if not node.get("children"): return 1
        return 1 + max(self._tree_depth(c) for c in node["children"])

    # 以降はオリジナルの複雑な描画ロジックをそのまま移行し、型ヒントを追加
    def _draw_singlelayer(self, cw: int, ch: int, usable_h: int, margin_top: int, node_w: int, overlay_size: Tuple[int, int], total: int, unclassified: int) -> None:
        left_x = 10
        right_x = cw - 150
        left_y0 = margin_top
        left_y1 = left_y0 + usable_h

        self.canvas.create_rectangle(left_x, left_y0, left_x + node_w, left_y1, fill="#34495E", outline="#2C3E50", tags="node")
        self.canvas.create_text(left_x + node_w // 2, left_y0 - 10, text=f"全体({total})", font=("Arial", 8, "bold"), fill="#2C3E50", tags="node")

        entries = []
        for i in range(self.state.num_classes):
            c_color = self.state.class_colors_used[i] if i < len(self.state.class_colors_used) else "#999"
            entries.append((i, self.state.class_names[i].get(), self.state.class_counts[i], c_color))
        if unclassified > 0:
            entries.append((-1, "未分類", unclassified, "#BDC3C7"))

        positions = self._calc_node_positions(entries, usable_h, margin_top)
        self._draw_nodes_and_flows(entries, positions, left_x, left_y0, usable_h, node_w, right_x, total, overlay_size)
        self.canvas.tag_raise("node")
        self.canvas.tag_raise("label")

    def _draw_recursive_multilayer(self, tree: Dict[str, Any], cw: int, ch: int, usable_h: int, margin_top: int, node_w: int, overlay_size: Tuple[int, int], total: int, unclassified: int, depth: int) -> None:
        num_cols = depth
        left_x = 10
        right_x = cw - 150
        
        step_x = (right_x - left_x) / (num_cols - 1) if num_cols > 1 else 0
        x_positions = [int(left_x + step_x * d) for d in range(num_cols)]

        left_y0 = margin_top
        left_y1 = left_y0 + usable_h
        self.canvas.create_rectangle(left_x, left_y0, left_x + node_w, left_y1, fill="#34495E", outline="#2C3E50", tags="node")
        self.canvas.create_text(left_x + node_w // 2, left_y0 - 10, text=f"全体({total})", font=("Arial", 8, "bold"), fill="#2C3E50", tags="node")

        for col in range(1, num_cols):
            self.canvas.create_text(x_positions[col] + node_w // 2, margin_top - 12, text=f"{col}回目分類", font=("Arial", 9, "bold"), fill="#34495E", tags="node")

        unclassified_entry = None
        if unclassified > 0:
            unclassified_entry = (-1, "未分類", unclassified, "#BDC3C7", None, None)

        first_layer_entries = []
        for child in tree.get("children", []):
            idx = child.get("class_idx")
            child_total = child.get("count", 0)
            name = child.get("name", "")
            c_color = self.state.class_colors_used[idx] if idx is not None and idx < len(self.state.class_colors_used) else "#999"
            mid_overlay = self._create_mid_overlay(child)
            first_layer_entries.append((idx, name, child_total, c_color, child, mid_overlay))
        
        if unclassified_entry:
            first_layer_entries.append(unclassified_entry)

        self._recurse_draw_layer(first_layer_entries, left_x, x_positions, 1, margin_top, usable_h, node_w, total, overlay_size)

        self.canvas.tag_raise("node")
        self.canvas.tag_raise("label")

    def _recurse_draw_layer(self, entries: List[Any], src_x: int, x_positions: List[int], current_col: int, margin_top: int, usable_h: int, node_w: int, parent_total: int, overlay_size: Tuple[int, int]) -> None:
        if not entries:
            return
            
        dst_x = x_positions[current_col]
        positions = self._calc_node_positions([(e[0], e[1], e[2], e[3]) for e in entries], usable_h, margin_top)
        
        for i, ((idx, name, cnt, color, child_node, mid_overlay), (ny0, ny1)) in enumerate(zip(entries, positions)):
            self.canvas.create_rectangle(dst_x, ny0, dst_x + node_w, ny1, fill=color, outline=self._darken(color), tags="node")
            label_x = dst_x + node_w + 3
            
            disp_overlay = mid_overlay
            if child_node is None or not child_node.get("children"):
                if idx >= 0 and idx < len(self.state.class_overlays) and self.state.class_overlays[idx]:
                    disp_overlay = self.state.class_overlays[idx]
            
            if disp_overlay:
                disp = disp_overlay.copy()
                disp.thumbnail(overlay_size)
                tk_ov = ImageTk.PhotoImage(disp)
                self.state.overlay_tks.append(tk_ov)
                mid_y = (ny0 + ny1) // 2
                self.canvas.create_image(label_x + overlay_size[0] // 2, mid_y, image=tk_ov, anchor="center", tags="node")
                label_x += overlay_size[0] + 3

            label_y = (ny0 + ny1) // 2
            self.canvas.create_text(label_x+1, label_y+1, text=f"{name}({cnt})", font=("Arial", 7), anchor="w", fill="white", tags="label")
            self.canvas.create_text(label_x-1, label_y-1, text=f"{name}({cnt})", font=("Arial", 7), anchor="w", fill="white", tags="label")
            self.canvas.create_text(label_x+1, label_y-1, text=f"{name}({cnt})", font=("Arial", 7), anchor="w", fill="white", tags="label")
            self.canvas.create_text(label_x-1, label_y+1, text=f"{name}({cnt})", font=("Arial", 7), anchor="w", fill="white", tags="label")
            self.canvas.create_text(label_x, label_y, text=f"{name}({cnt})", font=("Arial", 7), anchor="w", fill="#333", tags="label")

        self._draw_flows_only(entries, positions, src_x, margin_top, usable_h, node_w, dst_x, parent_total)

        for i, ((idx, name, cnt, color, child_node, _), (ny0, ny1)) in enumerate(zip(entries, positions)):
            sub_children = child_node.get("children", []) if child_node else []
            if sub_children and current_col + 1 < len(x_positions):
                sub_entries = []
                for gc in sub_children:
                    gc_idx, gc_cnt, gc_name = gc.get("class_idx"), gc.get("count", 0), gc.get("name", "")
                    gc_color = self.state.class_colors_used[gc_idx] if gc_idx is not None and gc_idx < len(self.state.class_colors_used) else "#999"
                    gc_mid_overlay = self._create_mid_overlay(gc)
                    sub_entries.append((gc_idx, gc_name, gc_cnt, gc_color, gc, gc_mid_overlay))
                
                sub_h = ny1 - ny0
                self._recurse_draw_layer(sub_entries, dst_x, x_positions, current_col + 1, ny0, sub_h, node_w, cnt, overlay_size)
            elif not sub_children and current_col + 1 < len(x_positions):
                pass_entry = [(idx, name, cnt, color, None, None)]
                sub_h = ny1 - ny0
                self._recurse_draw_layer(pass_entry, dst_x, x_positions, current_col + 1, ny0, sub_h, node_w, cnt, overlay_size)

    def _draw_flows_only(self, entries: List[Any], positions: List[Tuple[float, float]], src_x: float, src_y0: float, src_h: float, node_w: float, dst_x: float, total: int) -> None:
        src_cy = src_y0
        for entry, (ny0, ny1) in zip(entries, positions):
            cnt = entry[2]
            color = entry[3]
            if cnt > 0 and total > 0:
                flow_h = max(int(cnt / total * src_h), 2)
                ly0, ly1 = src_cy, src_cy + flow_h
                pts = self._sankey_flow_points(src_x + node_w, ly0, ly1, dst_x, ny0, ny1)
                light = self._lighten(color, 0.55)
                self.canvas.create_polygon(pts, fill=light, outline="", smooth=True, tags="flow")
                self.canvas.create_line(self._sankey_edge_points(src_x + node_w, ly0, dst_x, ny0), fill=color, width=1, smooth=True, tags="flow")
                self.canvas.create_line(self._sankey_edge_points(src_x + node_w, ly1, dst_x, ny1), fill=color, width=1, smooth=True, tags="flow")
                src_cy += flow_h

    def _calc_node_positions(self, entries: List[Any], usable_h: int, margin_top: int) -> List[Tuple[float, float]]:
        total = sum(e[2] for e in entries) or 1
        gap = 3
        available = usable_h - (gap * max(len(entries) - 1, 0))
        positions = []
        cy = float(margin_top)
        for entry in entries:
            cnt = entry[2]
            h = max(int(cnt / total * available), 6) if cnt > 0 else 4
            positions.append((cy, cy + h))
            cy += h + gap
        return positions

    def _draw_nodes_and_flows(self, entries: List[Any], positions: List[Tuple[float, float]], src_x: float, src_y0: float, src_h: float, node_w: float, dst_x: float, total: int, overlay_size: Tuple[int, int]) -> None:
        src_cy = src_y0
        for i, (entry, (ny0, ny1)) in enumerate(zip(entries, positions)):
            idx, name, cnt, color = entry[0], entry[1], entry[2], entry[3]
            self.canvas.create_rectangle(dst_x, ny0, dst_x + node_w, ny1, fill=color, outline=self._darken(color), tags="node")
            label_x = dst_x + node_w + 3
            
            if idx >= 0 and idx < len(self.state.class_overlays) and self.state.class_overlays[idx]:
                disp = self.state.class_overlays[idx].copy()
                disp.thumbnail(overlay_size)
                tk_ov = ImageTk.PhotoImage(disp)
                self.state.overlay_tks.append(tk_ov) 
                mid_y = (ny0 + ny1) // 2
                self.canvas.create_image(label_x + overlay_size[0] // 2, mid_y, image=tk_ov, anchor="center", tags="node")
                label_x += overlay_size[0] + 3

            label_y = (ny0 + ny1) // 2
            self.canvas.create_text(label_x+1, label_y+1, text=f"{name}({cnt})", font=("Arial", 7), anchor="w", fill="white", tags="label")
            self.canvas.create_text(label_x-1, label_y-1, text=f"{name}({cnt})", font=("Arial", 7), anchor="w", fill="white", tags="label")
            self.canvas.create_text(label_x+1, label_y-1, text=f"{name}({cnt})", font=("Arial", 7), anchor="w", fill="white", tags="label")
            self.canvas.create_text(label_x-1, label_y+1, text=f"{name}({cnt})", font=("Arial", 7), anchor="w", fill="white", tags="label")
            self.canvas.create_text(label_x, label_y, text=f"{name}({cnt})", font=("Arial", 7), anchor="w", fill="#333", tags="label")

            if cnt > 0 and total > 0:
                flow_h = max(int(cnt / total * src_h), 2)
                ly0, ly1 = src_cy, src_cy + flow_h
                pts = self._sankey_flow_points(src_x + node_w, ly0, ly1, dst_x, ny0, ny1)
                light = self._lighten(color, 0.55)
                self.canvas.create_polygon(pts, fill=light, outline="", smooth=True, tags="flow")
                self.canvas.create_line(self._sankey_edge_points(src_x + node_w, ly0, dst_x, ny0), fill=color, width=1, smooth=True, tags="flow")
                self.canvas.create_line(self._sankey_edge_points(src_x + node_w, ly1, dst_x, ny1), fill=color, width=1, smooth=True, tags="flow")
                src_cy += flow_h

    def _create_mid_overlay(self, node: Dict[str, Any]) -> Optional[Image.Image]:
        indices = self._get_all_leaf_class_indices(node)
        if not indices: return None
        
        base = None
        for c_idx in indices:
            if c_idx < len(self.state.class_overlays) and self.state.class_overlays[c_idx]:
                ov = self.state.class_overlays[c_idx]
                if base is None:
                    base = ov.copy()
                else:
                    if ov.size != base.size:
                        ov = ov.resize(base.size, Image.NEAREST)
                    base = Image.alpha_composite(base, ov)
        return base

    def _get_all_leaf_class_indices(self, node: Dict[str, Any]) -> List[int]:
        indices = []
        if not node.get("children"):
            idx = node.get("class_idx")
            if idx is not None: indices.append(idx)
        else:
            for child in node.get("children", []):
                indices.extend(self._get_all_leaf_class_indices(child))
        return indices

    def _sankey_flow_points(self, x0: float, y0_top: float, y0_bot: float, x1: float, y1_top: float, y1_bot: float) -> List[float]:
        n = 20
        mx = (x0 + x1) / 2
        top = [((1-t/n)**3*x0 + 3*(1-t/n)**2*(t/n)*mx + 3*(1-t/n)*(t/n)**2*mx + (t/n)**3*x1,
                (1-t/n)**3*y0_top + 3*(1-t/n)**2*(t/n)*y0_top + 3*(1-t/n)*(t/n)**2*y1_top + (t/n)**3*y1_top) for t in range(n+1)]
        bot = [((1-t/n)**3*x1 + 3*(1-t/n)**2*(t/n)*mx + 3*(1-t/n)*(t/n)**2*mx + (t/n)**3*x0,
                (1-t/n)**3*y1_bot + 3*(1-t/n)**2*(t/n)*y1_bot + 3*(1-t/n)*(t/n)**2*y0_bot + (t/n)**3*y0_bot) for t in range(n+1)]
        return [pt for sub in (top + bot) for pt in sub]

    # ==========================================
    # ツリーダイアグラム用の描画ロジック追加部 (縦方向・ボックス内包型)
    # ==========================================

    def _draw_tree(self, cw: int, ch: int, usable_h: int, margin_top: int, node_w: int, overlay_size: Tuple[int, int], total: int, unclassified: int, depth: int, tree: Optional[Dict[str, Any]]) -> None:
        """ツリー構造（組織図スタイル）を上から下へ構築し描画します。"""
        # --- 基本レイアウトパラメータ ---
        box_w = 120    # 1ノードあたりの横幅
        box_h = 96     # 1ノードあたりの縦幅
        gap_x = 20     # 横のノード同士の隙間
        gap_y = 60     # 縦のノード同士の隙間
        start_y = margin_top

        # 全体(ルート)ノードの定義
        root_entry = {
            "idx": None,
            "name": "全体",
            "cnt": total,
            "color": "#34495E",
            "node_dict": tree,
            "mid_overlay": self._create_mid_overlay(tree) if tree else None,
            "is_unclassified": False
        }

        # ツリー構造を1Dリストへフラット化 (`row`等をもたせる)
        flat_nodes = self._build_flat_tree(root_entry, current_row=0)
        
        # 未分類が存在する場合はルート直下の別ノードとして追加
        if unclassified > 0:
            unclassified_entry = {
                "idx": -1,
                "name": "未分類",
                "cnt": unclassified,
                "color": "#BDC3C7",
                "node_dict": None,
                "mid_overlay": None,
                "is_unclassified": True,
                "row": 1,
                "parent": flat_nodes[0]
            }
            flat_nodes.append(unclassified_entry)
            flat_nodes[0].setdefault("children_nodes", []).append(unclassified_entry)

        # 全体の横幅（X座標）をボトムアップで計算
        self._layout_tree_x(flat_nodes[0], 0.0, box_w, gap_x)

        # 計算されたX座標は0基準なので、キャンバスの幅に合わせてセンタリングする
        tree_width = flat_nodes[0].get("subtree_width", box_w)
        offset_x = max(10, (cw - tree_width) / 2)
        
        # 最終的なX, Y座標の確定
        self._assign_final_coordinates(flat_nodes[0], offset_x, start_y, box_h, gap_y)

        # 描画 (1. 線 -> 2. ボックス+中身 の順)
        self._draw_tree_edges(flat_nodes[0], box_w, box_h)
        self._draw_tree_nodes(flat_nodes, box_w, box_h, overlay_size)

        self.canvas.tag_raise("node")
        self.canvas.tag_raise("label")

    def _build_flat_tree(self, node_info: Dict[str, Any], current_row: int) -> List[Dict[str, Any]]:
        """再帰ツリー階層を展開し、描画用のフラットなリスト構造を作成する（縦方向用）。"""
        node_info["row"] = current_row
        node_info["children_nodes"] = []
        
        flat_list = [node_info]
        
        tree_dict = node_info.get("node_dict")
        if tree_dict and tree_dict.get("children"):
            for child in tree_dict["children"]:
                idx = child.get("class_idx")
                cnt = child.get("count", 0)
                name = child.get("name", "")
                c_color = self.state.class_colors_used[idx] if idx is not None and idx < len(self.state.class_colors_used) else "#999"
                mid_overlay = self._create_mid_overlay(child)
                
                child_info = {
                    "idx": idx,
                    "name": name,
                    "cnt": cnt,
                    "color": c_color,
                    "node_dict": child,
                    "mid_overlay": mid_overlay,
                    "is_unclassified": False,
                    "parent": node_info
                }
                
                node_info["children_nodes"].append(child_info)
                flat_list.extend(self._build_flat_tree(child_info, current_row + 1))
                
        return flat_list

    def _layout_tree_x(self, node: Dict[str, Any], start_x: float, box_w: float, gap_x: float) -> float:
        """ボトムアップで各ノードの配置幅(subtree_width)と相対X座標を計算します。
        戻り値は「このサブツリーが使い終わった直後の次のX座標」。
        """
        children = node.get("children_nodes", [])
        if not children:
            # 葉ノード
            node["x_rel"] = start_x
            node["subtree_width"] = box_w
            return start_x + box_w + gap_x
        
        # 子がいる場合、子のX座標を先に計算 (Bottom-Up)
        next_x = start_x
        for child in children:
            next_x = self._layout_tree_x(child, next_x, box_w, gap_x)
            
        # 親のX座標は、両端の子ノードの中央
        first_child_x = children[0]["x_rel"]
        last_child_x = children[-1]["x_rel"]
        
        node["x_rel"] = (first_child_x + last_child_x) / 2
        # サブツリー全体の幅
        node["subtree_width"] = (last_child_x + box_w) - start_x
        
        return next_x

    def _assign_final_coordinates(self, node: Dict[str, Any], offset_x: float, start_y: float, box_h: float, gap_y: float) -> None:
        """相対X座標にオフセットを足し、Y座標を計算して最終的な絶対座標(x,y)を決定します。"""
        node["x"] = node["x_rel"] + offset_x
        node["y"] = start_y + node["row"] * (box_h + gap_y)
        
        for child in node.get("children_nodes", []):
            self._assign_final_coordinates(child, offset_x, start_y, box_h, gap_y)

    def _draw_tree_edges(self, node: Dict[str, Any], box_w: float, box_h: float) -> None:
        """直角の折れ線（ステップライン）を縦方向に描画して接続する。"""
        children = node.get("children_nodes", [])
        if not children:
            return
            
        # 親の下部中央
        src_x = node["x"] + box_w / 2
        src_y = node["y"] + box_h
        
        # 親から下へ少し直線を伸ばす (マージンの半分)
        mid_y = src_y + 30
        
        for child in children:
            # 子の上部中央
            dst_x = child["x"] + box_w / 2
            dst_y = child["y"]
            color = child["color"]
            
            # 直角の折れ線を描画 (src_x, src_y) -> (src_x, mid_y) -> (dst_x, mid_y) -> (dst_x, dst_y)
            points = [src_x, src_y, src_x, mid_y, dst_x, mid_y, dst_x, dst_y]
            # 最上位など色が暗いものがあるため色は少し透過性のあるグレー (#888) または親の色などで引く
            edge_color = "#555" if node["idx"] is None else self._darken(node["color"], 0.1)
            self.canvas.create_line(points, fill=edge_color, width=1.5, tags="flow")
            
            self._draw_tree_edges(child, box_w, box_h)

    def _draw_tree_nodes(self, flat_nodes: List[Dict[str, Any]], box_w: float, box_h: float, overlay_size: Tuple[int, int]) -> None:
        """スケッチに基づき、白抜きの大きな枠内にテキストと画像を配置する。上部にはヘッダ的なカラーラベルを付ける。"""
        for n in flat_nodes:
            nx = n["x"]
            ny0 = n["y"]
            nx1 = nx + box_w
            ny1 = ny0 + box_h
            base_color = n["color"]
            name = n["name"]
            cnt = n["cnt"]
            
            # 1. 外側の枠（白地、黒またはグレー縁）
            self.canvas.create_rectangle(nx, ny0, nx1, ny1, fill="white", outline="#999", width=1, tags="node")
            
            # 2. 上部のインジケーター（そのクラスの色を示す細い帯）
            self.canvas.create_rectangle(nx, ny0, nx1, ny0 + 4, fill=base_color, outline="", tags="node")

            # 3. テキストラベル (中央上寄り)
            text_str = f"{name}({cnt})"
            mid_x = nx + box_w / 2
            
            # 全体ルートも含めて共通のサイズで上部に配置
            self.canvas.create_text(mid_x, ny0 + 16, text=text_str, font=("Arial", 9), fill="#333", tags="label")
            
            # 4. 画像オーバーレイ表示 (枠の中央下部)
            disp_overlay = n.get("mid_overlay")
            idx = n.get("idx")
            child_nodes = n.get("children_nodes", [])
            
            if idx is not None and idx >= 0 and not child_nodes:
                if idx < len(self.state.class_overlays) and self.state.class_overlays[idx]:
                    disp_overlay = self.state.class_overlays[idx]
            
            if disp_overlay:
                disp = disp_overlay.copy()
                disp.thumbnail(overlay_size)
                tk_ov = ImageTk.PhotoImage(disp)
                self.state.overlay_tks.append(tk_ov) # Reference Keep
                
                # ボックス内の中心(テキストと割合の間)に配置
                img_y = ny0 + 54
                self.canvas.create_image(mid_x, img_y, image=tk_ov, anchor="center", tags="node")
            
            # 5. 画像の下(ボックスの最下部)に割合(%)を表示
            # flat_nodes[0]["cnt"] がルートの全体数となる
            total_cnt = flat_nodes[0]["cnt"]
            if total_cnt > 0:
                pct = (cnt / total_cnt) * 100
                pct_str = f"{pct:.1f}%"
            else:
                pct_str = "0.0%"
            
            self.canvas.create_text(mid_x, ny1 - 6, text=pct_str, font=("Arial", 7), fill="#666", tags="label")


    def _draw_stacked_bar(self, cw: int, ch: int, usable_h: int, margin_top: int, overlay_size: Tuple[int, int], total: int, unclassified: int, depth: int, tree: Optional[Dict[str, Any]]) -> None:
        """縦軸100%の積み上げ棒グラフを描画します。"""
        if total <= 0:
            return

        box_w = 100
        gap_x = 40
        num_cols = depth
        
        # キャンバスの中央寄りにするための計算
        total_w = num_cols * box_w + (num_cols - 1) * gap_x
        start_x = max(60, (cw - total_w) / 2)
        
        y_bottom = margin_top + usable_h
        y_top = margin_top

        # Y軸（0% - 100%）
        self.canvas.create_line(start_x - 10, y_top, start_x - 10, y_bottom, fill="#999")
        for i in range(11):
            pct = i * 10
            y = y_bottom - (usable_h * pct / 100)
            self.canvas.create_line(start_x - 12, y, start_x - 8, y, fill="#999")
            self.canvas.create_text(start_x - 15, y, text=f"{pct}%", font=("Arial", 8), anchor="e", fill="#666")

        layers = [[] for _ in range(num_cols)]
        
        def get_slice(node, current_d, target_d, result_list):
            if current_d == target_d:
                idx = node.get("class_idx")
                cnt = node.get("count", 0)
                if cnt > 0 and idx is not None:
                    result_list.append({
                        "idx": idx,
                        "name": node.get("name", ""),
                        "cnt": cnt,
                        "color": self.state.class_colors_used[idx] if idx < len(self.state.class_colors_used) else "#999",
                        "mid_overlay": self._create_mid_overlay(node)
                    })
            else:
                children = node.get("children", [])
                if children:
                    for child in children:
                        get_slice(child, current_d + 1, target_d, result_list)
                else:
                    if node.get("name") != "全体":
                        idx = node.get("class_idx")
                        cnt = node.get("count", 0)
                        if cnt > 0 and idx is not None:
                            result_list.append({
                                "idx": idx,
                                "name": node.get("name", ""),
                                "cnt": cnt,
                                "color": self.state.class_colors_used[idx] if idx < len(self.state.class_colors_used) else "#999",
                                "mid_overlay": self._create_mid_overlay(node)
                            })

        if tree and tree.get("children"):
            for col in range(num_cols):
                get_slice(tree, 0, col + 1, layers[col])
        else:
            for i in range(self.state.num_classes):
                cnt = self.state.class_counts[i]
                if cnt > 0:
                    layers[0].append({
                        "idx": i,
                        "name": self.state.class_names[i].get(),
                        "cnt": cnt,
                        "color": self.state.class_colors_used[i] if i < len(self.state.class_colors_used) else "#999",
                        "mid_overlay": self.state.class_overlays[i] if i < len(self.state.class_overlays) else None
                    })

        for col in range(num_cols):
            x = start_x + col * (box_w + gap_x)
            
            title = f"{col+1}回目分類" if num_cols > 1 else "分類結果"
            self.canvas.create_text(x + box_w/2, y_top - 15, text=title, font=("Arial", 9, "bold"), fill="#333", tags="label")
            
            layer_nodes = layers[col]
            layer_total = sum(n["cnt"] for n in layer_nodes)
            layer_unclassified = max(total - layer_total, 0)
            
            render_nodes = list(layer_nodes)
            if layer_unclassified > 0:
                render_nodes.append({
                    "idx": -1, "name": "未分類", "cnt": layer_unclassified, "color": "#BDC3C7", "mid_overlay": None
                })
            
            current_y = y_bottom
            for n in render_nodes:
                cnt = n["cnt"]
                if cnt == 0: continue
                
                h = (cnt / total) * usable_h
                next_y = current_y - h
                
                # 矩形
                self.canvas.create_rectangle(x, next_y, x + box_w, current_y, fill=n["color"], outline=self._darken(n["color"]), tags="node")
                
                # ラベル
                if h > 15:
                    pct_str = f"{(cnt / total)*100:.1f}%"
                    label_str = f"{n['name']}\n{pct_str}" if h > 30 else pct_str
                    mid_y = (current_y + next_y) / 2
                    
                    # サムネイル表示可能な領域高さの場合
                    if h > overlay_size[1] + 30 and n.get("mid_overlay"):
                        disp = n["mid_overlay"].copy()
                        disp.thumbnail(overlay_size)
                        tk_ov = ImageTk.PhotoImage(disp)
                        self.state.overlay_tks.append(tk_ov)
                        
                        img_y = mid_y - 12
                        self.canvas.create_image(x + box_w/2, img_y, image=tk_ov, anchor="center", tags="node")
                        
                        text_y = mid_y + overlay_size[1]/2 + 2
                        self.canvas.create_text(x + box_w/2+1, text_y+1, text=label_str, font=("Arial", 8, "bold"), fill="#333", justify="center", tags="label")
                        self.canvas.create_text(x + box_w/2, text_y, text=label_str, font=("Arial", 8, "bold"), fill="white", justify="center", tags="label")
                    else:
                        self.canvas.create_text(x + box_w/2+1, mid_y+1, text=label_str, font=("Arial", 8, "bold"), fill="#333", justify="center", tags="label")
                        self.canvas.create_text(x + box_w/2, mid_y, text=label_str, font=("Arial", 8, "bold"), fill="white", justify="center", tags="label")
                
                current_y = next_y


    def _sankey_edge_points(self, x0: float, y0: float, x1: float, y1: float) -> List[float]:
        n = 20
        mx = (x0 + x1) / 2
        return [pt for t in range(n+1) for pt in ((1-t/n)**3*x0 + 3*(1-t/n)**2*(t/n)*mx + 3*(1-t/n)*(t/n)**2*mx + (t/n)**3*x1,
                                                  (1-t/n)**3*y0 + 3*(1-t/n)**2*(t/n)*y0 + 3*(1-t/n)*(t/n)**2*y1 + (t/n)**3*y1)]

    def _lighten(self, hex_color: str, factor: float = 0.5) -> str:
        r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
        r, g, b = int(r+(255-r)*factor), int(g+(255-g)*factor), int(b+(255-b)*factor)
        return f"#{r:02x}{g:02x}{b:02x}"

    def _darken(self, hex_color: str, factor: float = 0.2) -> str:
        r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
        r, g, b = int(r*(1-factor)), int(g*(1-factor)), int(b*(1-factor))
        return f"#{r:02x}{g:02x}{b:02x}"
