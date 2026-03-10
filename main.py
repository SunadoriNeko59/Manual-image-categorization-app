import tkinter as tk
from src.ui.main_window import ImageMultiClassApp
from src.utils.logger import logger

def main():
    """アプリケーションのエントリーポイント"""
    logger.info("アプリケーションを起動します")
    try:
        root = tk.Tk()
        app = ImageMultiClassApp(root)
        root.mainloop()
        logger.info("アプリケーションを正常に終了しました")
    except Exception as e:
        logger.error(f"予期せぬエラーが発生しました: {e}", exc_info=True)

if __name__ == "__main__":
    main()
