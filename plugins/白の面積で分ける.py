import numpy as np
from PIL import Image
from typing import List, Any

# 型ヒント用 (実際には実行時に main_window 等から呼ばれるため、importエラーにならないようにAnyを使います)
def classify(images: List[Image.Image], state: Any, k: int) -> List[int]:
    """
    画像の「白いピクセルの数（面積）」を計算し、その面積順で並べ替え、
    等分割してK個のクラスに分類するサンプルプラグインです。
    
    Args:
        images: 分類対象のPIL画像のリスト (Lモード・RGBモード混在の可能性あり)
        state: AppStateインスタンス (現在のUI状態や他の値が必要な場合に利用)
        k: 分割したいクラス数
        
    Returns:
        各画像の所属するクラスインデックス（0 ~ k-1）を含むリスト
    """
    # 1. 各画像の白色ピクセル数を計算
    areas = []
    for img in images:
        gray = img.convert("L")
        arr = np.array(gray)
        # 閾値128を超えるピクセルを白とみなして数をカウント
        white_count = np.sum(arr > 128)
        areas.append(white_count)
        
    # もし画像が1枚もない場合は空リストを返す
    if not areas:
        return []
        
    # 2. 面積の最小値と最大値を元に、K等分するための境界を計算
    min_area = min(areas)
    max_area = max(areas)
    
    # 全部同じ面積の場合は K等分できないので、とりあえず全部クラス0に入れる
    if min_area == max_area:
        return [0] * len(images)
        
    # 1クラスあたりのステップ幅
    step = (max_area - min_area) / k
    
    labels = []
    for area in areas:
        # この画像がどのクラス範囲に属するか計算
        label = int((area - min_area) / step)
        
        # 境界値の最大値ぴったりだとインデックスがkになってしまうため、(k-1)に丸める
        label = min(label, k - 1)
        labels.append(label)
        
    return labels
