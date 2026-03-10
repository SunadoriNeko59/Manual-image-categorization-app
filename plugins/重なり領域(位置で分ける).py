import numpy as np
from PIL import Image
from scipy import ndimage
from typing import List, Optional, Any

def classify(images: List[Image.Image], k: int, state: Any) -> Optional[List[int]]:
    """全画像を重ね合わせてヒートマップを作り、強く重なっている「コア領域」を抽出して分類します。"""
    if not images:
        return []

    ref_size = images[0].size
    heatmap = np.zeros((ref_size[1], ref_size[0]), dtype=np.float64)
    dilated_arrays = []
    
    # stateから膨張率を取得（なければデフォルト1.0%）
    dilation_pct = 1.0
    if hasattr(state, 'overlap_dilation_pct') and state.overlap_dilation_pct:
        dilation_pct = state.overlap_dilation_pct.get()
        
    iterations = max(2, int(max(ref_size) * (dilation_pct / 100.0)))
    
    for img in images:
        gray = img.convert("L").resize(ref_size)
        arr = (np.array(gray) > 128)
        dilated = ndimage.binary_dilation(arr, iterations=iterations).astype(np.float64)
        heatmap += dilated
        dilated_arrays.append(dilated)

    max_overlap = heatmap.max()
    threshold = max(2.0, max_overlap * 0.4)
    if max_overlap < 2.0:
        threshold = max_overlap * 0.5

    binary_map = (heatmap >= threshold).astype(np.int32)
    labeled, num_features = ndimage.label(binary_map)

    if num_features < k:
        threshold = max(1.0, threshold * 0.5)
        binary_map = (heatmap >= threshold).astype(np.int32)
        labeled, num_features = ndimage.label(binary_map)

    if num_features == 0:
        return None

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
        for ci, r_id in enumerate(top_k):
            intersection = np.sum(arr * (labeled == r_id))
            if intersection > best_score:
                best_score = intersection
                best_class = ci
        labels.append(best_class)
            
    return labels
