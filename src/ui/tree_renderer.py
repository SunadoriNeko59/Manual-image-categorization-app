import tkinter as tk
from PIL import Image, ImageTk
from typing import List, Tuple, Dict, Any, Optional

from ..core.state import AppState
from .constants import OVERLAY_THUMB

class TreeRenderer:
    """ツリーダイアグラムを描画する専用のレンダラークラス。
    
    キャンバスとAppStateを受け取り、現在の分類結果をツリー構造で視覚化します。
    """
    def __init__(self, canvas: tk.Canvas, state: AppState):
        self.canvas = canvas
        self.state = state

    def draw(self) -> None:
        """キャンバスをクリアし、現在の状態に基づいてツリーダイアグラムを再描画します。"""
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
        overlay_size = OVERLAY_THUMB

        tree = self.state.classification_tree
        if tree and tree.get("children"):
            self._update_tree_counts(tree)
            self._update_tree_names(tree)
            depth = self._tree_depth(tree)
        else:
            depth = 1

        # ツリーダイアグラムの描画
        self._draw_tree(cw, ch, usable_h, margin_top, overlay_size, total, unclassified, depth, tree)

        # 描画された要素全体を囲むようにスクロール領域を更新
        bbox = self.canvas.bbox("all")
        if bbox:
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

    def _draw_tree(self, cw: int, ch: int, usable_h: int, margin_top: int, overlay_size: Tuple[int, int], total: int, unclassified: int, depth: int, tree: Optional[Dict[str, Any]]) -> None:
        """ツリー構造（組織図スタイル）を上から下へ構築し描画します。"""
        box_w = 120    # 1ノードあたりの横幅
        box_h = 96     # 1ノードあたりの縦幅
        gap_x = 20     # 横のノード同士の隙間
        gap_y = 60     # 縦のノード同士の隙間
        start_y = margin_top

        root_entry = {
            "idx": None,
            "name": "全体",
            "cnt": total,
            "color": "#34495E",
            "node_dict": tree,
            "mid_overlay": self._create_mid_overlay(tree) if tree else None,
            "is_unclassified": False
        }

        flat_nodes = self._build_flat_tree(root_entry, current_row=0)
        
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

        self._layout_tree_x(flat_nodes[0], 0.0, box_w, gap_x)

        tree_width = flat_nodes[0].get("subtree_width", box_w)
        offset_x = max(10, (cw - tree_width) / 2)
        
        self._assign_final_coordinates(flat_nodes[0], offset_x, start_y, box_h, gap_y)

        self._draw_tree_edges(flat_nodes[0], box_w, box_h)
        self._draw_tree_nodes(flat_nodes, box_w, box_h, overlay_size)

        self.canvas.tag_raise("node")
        self.canvas.tag_raise("label")

    def _build_flat_tree(self, node_info: Dict[str, Any], current_row: int) -> List[Dict[str, Any]]:
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
        children = node.get("children_nodes", [])
        if not children:
            node["x_rel"] = start_x
            node["subtree_width"] = box_w
            return start_x + box_w + gap_x
        
        next_x = start_x
        for child in children:
            next_x = self._layout_tree_x(child, next_x, box_w, gap_x)
            
        first_child_x = children[0]["x_rel"]
        last_child_x = children[-1]["x_rel"]
        
        node["x_rel"] = (first_child_x + last_child_x) / 2
        node["subtree_width"] = (last_child_x + box_w) - start_x
        
        return next_x

    def _assign_final_coordinates(self, node: Dict[str, Any], offset_x: float, start_y: float, box_h: float, gap_y: float) -> None:
        node["x"] = node["x_rel"] + offset_x
        node["y"] = start_y + node["row"] * (box_h + gap_y)
        
        for child in node.get("children_nodes", []):
            self._assign_final_coordinates(child, offset_x, start_y, box_h, gap_y)

    def _draw_tree_edges(self, node: Dict[str, Any], box_w: float, box_h: float) -> None:
        children = node.get("children_nodes", [])
        if not children:
            return
            
        src_x = node["x"] + box_w / 2
        src_y = node["y"] + box_h
        mid_y = src_y + 30
        
        for child in children:
            dst_x = child["x"] + box_w / 2
            dst_y = child["y"]
            
            points = [src_x, src_y, src_x, mid_y, dst_x, mid_y, dst_x, dst_y]
            edge_color = "#555" if node["idx"] is None else self._darken(node["color"], 0.1)
            self.canvas.create_line(points, fill=edge_color, width=1.5, tags="flow")
            
            self._draw_tree_edges(child, box_w, box_h)

    def _draw_tree_nodes(self, flat_nodes: List[Dict[str, Any]], box_w: float, box_h: float, overlay_size: Tuple[int, int]) -> None:
        for n in flat_nodes:
            nx = n["x"]
            ny0 = n["y"]
            nx1 = nx + box_w
            ny1 = ny0 + box_h
            base_color = n["color"]
            name = n["name"]
            cnt = n["cnt"]
            
            self.canvas.create_rectangle(nx, ny0, nx1, ny1, fill="white", outline="#999", width=1, tags="node")
            self.canvas.create_rectangle(nx, ny0, nx1, ny0 + 4, fill=base_color, outline="", tags="node")

            text_str = f"{name}({cnt})"
            mid_x = nx + box_w / 2
            self.canvas.create_text(mid_x, ny0 + 16, text=text_str, font=("Arial", 9), fill="#333", tags="label")
            
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
                self.state.overlay_tks.append(tk_ov) 
                
                img_y = ny0 + 54
                self.canvas.create_image(mid_x, img_y, image=tk_ov, anchor="center", tags="node")
            
            total_cnt = flat_nodes[0]["cnt"]
            if total_cnt > 0:
                pct = (cnt / total_cnt) * 100
                pct_str = f"{pct:.1f}%"
            else:
                pct_str = "0.0%"
            
            self.canvas.create_text(mid_x, ny1 - 6, text=pct_str, font=("Arial", 7), fill="#666", tags="label")

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

    def _darken(self, hex_color: str, factor: float = 0.2) -> str:
        r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
        r, g, b = int(r*(1-factor)), int(g*(1-factor)), int(b*(1-factor))
        return f"#{r:02x}{g:02x}{b:02x}"
