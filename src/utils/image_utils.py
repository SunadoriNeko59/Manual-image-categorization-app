import numpy as np
from PIL import Image

# 画像処理に関連する定数
WHITE_THRESHOLD = 200

def white_ratio(img: Image.Image, threshold: int = WHITE_THRESHOLD) -> float:
    """画像の白ピクセル（指定された閾値以上の明るさを持つピクセル）の割合を計算します。
    
    Args:
        img (PIL.Image.Image): 判定対象のPillow画像オブジェクト
        threshold (int): 白と判定する輝度の閾値 (0-255)
        
    Returns:
        float: 全ピクセルに対する白ピクセルの割合（0.0 〜 1.0）
    """
    # グレースケールに変換してからNumPy配列として処理
    gray = img.convert("L")
    arr = np.array(gray)
    
    # 閾値以上のピクセル数を全ピクセル数で割って割合を計算
    ratio = (arr >= threshold).sum() / arr.size
    return ratio
