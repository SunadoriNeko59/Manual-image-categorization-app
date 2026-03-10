import numpy as np
from PIL import Image
from typing import List, Any

def classify(images: List[Image.Image], mask_images: List[Image.Image]) -> List[int]:
    """指定されたマスク画像との重なり具合で分類します。"""
    if not images or not mask_images:
        return [0] * len(images)

    num_masks = len(mask_images)
    ref_size = images[0].size
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
            overlap = int(np.sum(img_arr & mask_arr))
            if overlap > best_overlap:
                best_overlap = overlap
                best_mask = mi
        
        if best_mask >= 0:
            labels.append(best_mask)
        else:
            labels.append(num_masks) # No Match
            
    return labels
