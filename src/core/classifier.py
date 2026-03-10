import numpy as np
from PIL import Image, ImageDraw
from sklearn.cluster import KMeans
from scipy import ndimage
from typing import List, Optional, Any

# 型ヒント用
from .state import AppState
from ..utils.logger import logger

class ImageClassifier:
    """画像の解析・クラスタリング、および赤色オーバーレイの生成を行うロジッククラス。
    
    UIに依存しない純粋な計算処理を担当します。
    """

    @staticmethod
    def binary_to_red_rgba(img: Image.Image, alpha: int) -> Image.Image:
        """2値化された画像から、白色部分を透明度付きの赤色に変換したRGBA画像を生成します。
        
        Args:
            img (Image.Image): 元画像
            alpha (int): 赤色の透明度 (0-255)
            
        Returns:
            Image.Image: 変換後のRGBA画像
        """
        gray = img.convert("L")
        w, h = gray.size
        # 透明な背景を持つRGBA画像を新規作成
        out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        
        g = gray.load()
        o = out.load()
        
        # 閾値128を超えた明るい（白い）ピクセルを赤色に置き換え
        for y in range(h):
            for x in range(w):
                if g[x, y] > 128:
                    o[x, y] = (255, 0, 0, alpha)
        return out

    @staticmethod
    def binary_to_yellow_rgba(img: Image.Image, alpha: int) -> Image.Image:
        """2値化された画像から、白色部分を透明度付きの黄色に変換したRGBA画像を生成します。
        
        マスク画像の可視化に使用されます。
        
        Args:
            img (Image.Image): マスク画像
            alpha (int): 黄色の透明度 (0-255)
            
        Returns:
            Image.Image: 変換後のRGBA画像
        """
        gray = img.convert("L")
        w, h = gray.size
        out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        
        g = gray.load()
        o = out.load()
        
        # 閾値128を超えた明るいピクセルを黄色(255, 255, 0)に置き換え
        for y in range(h):
            for x in range(w):
                if g[x, y] > 128:
                    o[x, y] = (255, 255, 0, alpha)
        return out

    @staticmethod
    def add_border(img: Image.Image, width: int = 2) -> Image.Image:
        """画像の周囲に黒い枠線を描画します。"""
        draw = ImageDraw.Draw(img)
        w, h = img.size
        for i in range(width):
            draw.rectangle([i, i, w - 1 - i, h - 1 - i], outline=(0, 0, 0, 255))
        return img

    @staticmethod
    def rebuild_overlay(state: AppState, c: int) -> None:
        """特定のクラス(c)に属する全ての画像の赤色オーバーレイを合成します。
        
        結果は state.class_overlays[c] に保存されます。
        """
        base: Optional[Image.Image] = None
        
        # クラスcにチェックが付いている画像を全て合成
        for img, vars_per_image in zip(state.images, state.class_vars):
            if vars_per_image[c].get():
                ov = ImageClassifier.binary_to_red_rgba(img, state.alpha.get() if state.alpha else 128)
                if base is None:
                    base = ov
                else:
                    # 画像サイズが合わない場合はリサイズして強制合成
                    if ov.size != base.size:
                        ov = ov.resize(base.size, Image.NEAREST)
                    base = Image.alpha_composite(base, ov)
                    
        # マスク画像が対応するクラスに設定されている場合、黄色半透明で合成
        if base and c in state.mask_overlays:
            mask_img = state.mask_overlays[c]
            yellow_ov = ImageClassifier.binary_to_yellow_rgba(
                mask_img, state.alpha.get() if state.alpha else 128
            )
            if yellow_ov.size != base.size:
                yellow_ov = yellow_ov.resize(base.size, Image.NEAREST)
            base = Image.alpha_composite(base, yellow_ov)
        elif not base and c in state.mask_overlays:
            # 画像がまだ割り当てられていなくてもマスクだけ表示
            mask_img = state.mask_overlays[c]
            ref_size = state.images[0].size if state.images else (120, 120)
            base = ImageClassifier.binary_to_yellow_rgba(
                mask_img.resize(ref_size) if mask_img.size != ref_size else mask_img,
                state.alpha.get() if state.alpha else 128
            )
            
        # 最後に枠線を追加
        if base:
            base = ImageClassifier.add_border(base)
            
        state.class_overlays[c] = base

    @staticmethod
    def rebuild_all_overlays(state: AppState) -> None:
        """全クラスに対してオーバーレイの再合成処理を実行します。"""
        for c in range(state.num_classes):
            ImageClassifier.rebuild_overlay(state, c)
