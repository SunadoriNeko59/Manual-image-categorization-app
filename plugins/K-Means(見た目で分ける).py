import numpy as np
from PIL import Image
from sklearn.cluster import KMeans
from typing import List, Any

def classify(images: List[Image.Image], k: int) -> List[int]:
    """画像を64x64に縮小し、ピクセル値全体を特徴量としてK-Meansクラスタリングを行います。"""
    features = []
    for img in images:
        # 画像全体の見た目の類似度で判定するため、低解像度に縮小して平坦化
        gray = img.convert("L").resize((64, 64))
        features.append(np.array(gray).flatten())
        
    X = np.array(features)
    kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X)
    return labels.tolist()
