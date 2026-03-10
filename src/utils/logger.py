import logging
import sys

def setup_logger(name: str = "ImageClassifierApp") -> logging.Logger:
    """アプリケーション共通のロガーを設定し、返す関数。
    
    Args:
        name (str): ロガーの名前 (デフォルト: "ImageClassifierApp")
        
    Returns:
        logging.Logger: 設定済みのロガーインスタンス
    """
    logger = logging.getLogger(name)
    
    # すでにハンドラが設定されている場合は、再設定を防ぐ
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        # コンソール出力用ハンドラ
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.INFO)
        
        # ログのフォーマット設定
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        
    return logger

# デフォルトのロガーインスタンスを作成してエクスポート
logger = setup_logger()
