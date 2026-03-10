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

    # ==========================================
    # クラスタリング（自動分類）アルゴリズム群
    # ==========================================

    @staticmethod
    def kmeans_cluster(images: List[Image.Image], k: int) -> List[int]:
        """画像を64x64に縮小し、ピクセル値全体を特徴量としてK-Meansクラスタリングを行います。
        （画像の全体的な見た目・形状の類似度で分類）
        """
        logger.info(f"K-Meansクラスタリングを開始: K={k}")
        features = []
        for img in images:
            gray = img.convert("L").resize((64, 64))
            features.append(np.array(gray).flatten())
            
        X = np.array(features)
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = kmeans.fit_predict(X)
        logger.info("K-Meansクラスタリングが完了しました")
        return labels.tolist()

    @staticmethod
    def overlap_cluster(images: List[Image.Image], k: int, dilation_pct: float = 1.0) -> Optional[List[int]]:
        """全画像を重ね合わせてヒートマップを作り、強く重なっている「コア領域」を抽出し、
        そこを基準に分類します。（膨張処理により近接する小さな点も結合して判定）
        """
        logger.info(f"強重なり領域ベースのクラスタリングを開始: K={k}")
        ref_size = images[0].size
        heatmap = np.zeros((ref_size[1], ref_size[0]), dtype=np.float64)
        dilated_arrays = []
        
        # 膨張の回数：画像サイズの約 dilation_pct %をベースとする（最低2ピクセル）
        iterations = max(2, int(max(ref_size) * (dilation_pct / 100.0)))
        
        for img in images:
            gray = img.convert("L").resize(ref_size)
            arr = (np.array(gray) > 128)
            # 小さな点が近い位置にある場合を考慮し、膨張処理で周囲と結合しやすくする
            dilated = ndimage.binary_dilation(arr, iterations=iterations).astype(np.float64)
            heatmap += dilated
            dilated_arrays.append(dilated)

        # 巨大なノイズ画像1枚に影響されないよう、
        # すべての画像を重ねて「多数が強く重なっている部分（コア）」を抽出する
        max_overlap = heatmap.max()
        # 最大重なり枚数の40%以上（最低2枚以上）重なっている領域をコアとする
        threshold = max(2.0, max_overlap * 0.4)
        
        if max_overlap < 2.0:
            # 全体的に全く重なりがない場合は閾値を緩和
            threshold = max_overlap * 0.5

        binary_map = (heatmap >= threshold).astype(np.int32)
        labeled, num_features = ndimage.label(binary_map)

        # 抽出されたコアが少なすぎる場合は閾値を下げて再試行
        if num_features < k:
            threshold = max(1.0, threshold * 0.5)
            binary_map = (heatmap >= threshold).astype(np.int32)
            labeled, num_features = ndimage.label(binary_map)

        if num_features == 0:
            logger.error("強く重なっているコア領域の抽出に失敗しました")
            return None # 失敗

        # 強く重なっている箇所が複数あった場合は個別のクラスとするため、
        # コアごとに「重なりの強さ(ヒートマップ値の合計)」を求め上位 K 個を取得する
        region_scores = []
        for r in range(1, num_features + 1):
            mask = (labeled == r)
            score = np.sum(heatmap[mask])
            region_scores.append((r, score))
        
        region_scores.sort(key=lambda x: x[1], reverse=True)
        top_k = [r_id for r_id, _ in region_scores[:k]]

        labels = []
        for arr in dilated_arrays:
            best_class = 0
            best_score = -1.0
            
            # 各画像が、上位K個のどのコア領域と最も強く交差しているかを比較
            for ci, r_id in enumerate(top_k):
                intersection = np.sum(arr * (labeled == r_id))
                if intersection > best_score:
                    best_score = intersection
                    best_class = ci
            
            labels.append(best_class)
            
        logger.info(f"強重なり領域ベースのクラスタリングが完了しました（コア抽出数: {num_features}）")
        return labels

    @staticmethod
    def whiteratio_cluster(white_ratios: List[float], k: int) -> List[int]:
        """白率の最小値〜最大値の間をK等分し、どのレンジに入るかで分類します。"""
        logger.info(f"白率範囲クラスタリングを開始: K={k}")
        min_r, max_r = min(white_ratios) * 100, max(white_ratios) * 100
        step = (max_r - min_r) / k if max_r > min_r else 1
        labels = []
        
        for ratio in white_ratios:
            ratio_pct = ratio * 100
            label = int((ratio_pct - min_r) / step)
            # 最大値丁度の場合はインデックスがはみ出ないように丸める
            label = min(label, k - 1)
            labels.append(label)
            
        return labels

    @staticmethod
    def whiteratio_zero_cluster(white_ratios: List[float]) -> List[int]:
        """白率が完全に0%か、それ以外(0%超)かで2つのクラスに分類します。"""
        logger.info("白率0%基準のクラスタリングを開始")
        return [0 if ratio == 0.0 else 1 for ratio in white_ratios]

    @staticmethod
    def border_white_cluster(images: List[Image.Image], threshold: int = 200) -> List[int]:
        """画像の外周（上下左右の辺）に指定閾値以上の白いピクセルが含まれるかで2クラスに分類します。"""
        logger.info("外周白ピクセル基準のクラスタリングを開始")
        labels = []
        for img in images:
            gray = img.convert("L")
            arr = np.array(gray)
            
            # 上端、下端、左端、右端のピクセルを抽出
            top_edge = arr[0, :]
            bottom_edge = arr[-1, :]
            left_edge = arr[:, 0]
            right_edge = arr[:, -1]
            
            # いずれかの辺に threshold 以上の白いピクセルが存在するか判定
            if (np.any(top_edge >= threshold) or np.any(bottom_edge >= threshold) or 
                np.any(left_edge >= threshold) or np.any(right_edge >= threshold)):
                labels.append(1)  # 外周に白あり
            else:
                labels.append(0)  # 外周に白なし
                
        return labels

    @staticmethod
    def mask_cluster(images: List[Image.Image], mask_images: List[Image.Image]) -> List[int]:
        """マスク画像の白領域と入力画像の白領域の重なりを判定して分類します。
        
        各入力画像に対し、全マスク画像との重なりピクセル数を計算し、
        最も重なりが大きいマスクに対応するクラスへ割り当てます。
        どのマスクとも重ならない画像は最後のクラス（No Match）に分類されます。
        
        Args:
            images: 入力画像のリスト
            mask_images: マスク画像のリスト（最大5枚）
            
        Returns:
            各画像のクラスラベルのリスト。
            クラス 0〜(len(mask_images)-1) がマスク対応、最後のクラスが「No Match」。
        """
        num_masks = len(mask_images)
        logger.info(f"マスク画像判定クラスタリングを開始: マスク数={num_masks}")
        
        # マスク画像を2値化配列に変換（閾値128）
        ref_size = images[0].size if images else (1, 1)
        mask_arrays = []
        for mask_img in mask_images:
            gray = mask_img.convert("L").resize(ref_size)
            mask_arr = (np.array(gray) > 128)
            mask_arrays.append(mask_arr)
        
        labels = []
        for img in images:
            gray = img.convert("L").resize(ref_size)
            img_arr = (np.array(gray) > 128)
            
            best_mask = -1
            best_overlap = 0
            
            for mi, mask_arr in enumerate(mask_arrays):
                # 入力画像とマスクの両方が白いピクセルの数を計算
                overlap = int(np.sum(img_arr & mask_arr))
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_mask = mi
            
            if best_mask >= 0:
                labels.append(best_mask)
            else:
                # どのマスクとも重ならない → No Match クラス（最後のクラス）
                labels.append(num_masks)
        
        logger.info(f"マスク画像判定クラスタリングが完了しました")
        return labels
