import numpy as np
from PIL import Image
from typing import List, Any

def classify(images: List[Image.Image]) -> List[int]:
    """白率（白色ピクセルの割合）が完全に0%か、それ以外かで分類します。"""
    labels = []
    for img in images:
        gray = img.convert("L")
        arr = np.array(gray)
        # 閾値128を超えるピクセルをカウント
        white_count = np.sum(arr > 128)
        labels.append(0 if white_count == 0 else 1)
    return labels
