import numpy as np
from PIL import Image
from typing import List, Any

def classify(images: List[Image.Image]) -> List[int]:
    """画像の外周（上下左右の端）に白いピクセルが含まれるかを判定します。"""
    threshold = 200
    labels = []
    for img in images:
        gray = img.convert("L")
        arr = np.array(gray)
        
        top_edge = arr[0, :]
        bottom_edge = arr[-1, :]
        left_edge = arr[:, 0]
        right_edge = arr[:, -1]
        
        if (np.any(top_edge >= threshold) or np.any(bottom_edge >= threshold) or 
            np.any(left_edge >= threshold) or np.any(right_edge >= threshold)):
            labels.append(1)  # 外周に白あり
        else:
            labels.append(0)  # 外周に白なし
                
    return labels
