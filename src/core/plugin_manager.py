import os
import sys
import importlib.util
from typing import Callable, Dict, List, Any
from PIL import Image

from ..utils.logger import logger
from .state import AppState

class PluginManager:
    """自動分類用の外部スクリプト(プラグイン)を動的に読み込み・管理するクラス。"""
    
    def __init__(self, plugins_dir: str = "plugins"):
        self.plugins_dir = plugins_dir
        self.plugins: Dict[str, Callable] = {}
        # アプリ起動時にロード
        self.load_plugins()

    def load_plugins(self) -> None:
        """指定されたディレクトリから.pyファイルを検索し、プラグイン関数として読み込む"""
        self.plugins.clear()
        
        # main.pyなどからの相対パスでも確実に見つけるために絶対パス化
        if not os.path.isabs(self.plugins_dir):
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            self.plugins_dir = os.path.join(base_dir, self.plugins_dir)
            
        if not os.path.exists(self.plugins_dir):
            try:
                os.makedirs(self.plugins_dir)
                logger.info(f"プラグインディレクトリを作成しました: {self.plugins_dir}")
            except Exception as e:
                logger.warning(f"プラグインディレクトリの作成に失敗しました: {e}")
                return

        for filename in os.listdir(self.plugins_dir):
            if filename.endswith(".py") and not filename.startswith("_"):
                plugin_name = os.path.splitext(filename)[0]
                filepath = os.path.join(self.plugins_dir, filename)
                
                try:
                    spec = importlib.util.spec_from_file_location(plugin_name, filepath)
                    if spec is None or spec.loader is None:
                        continue
                    
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[plugin_name] = module
                    spec.loader.exec_module(module)
                    
                    # 'classify' という名前の関数をエクスポートしているかチェック
                    if hasattr(module, 'classify') and callable(getattr(module, 'classify')):
                        self.plugins[plugin_name] = getattr(module, 'classify')
                        logger.info(f"プラグインをロードしました: {plugin_name}")
                    else:
                        logger.warning(f"プラグイン '{filename}' に 'classify(images, state, k)' 関数が見つかりません。")
                except Exception as e:
                    logger.error(f"プラグイン '{filename}' の読み込みに失敗しました: {e}")

    def get_plugin_names(self) -> List[str]:
        """ロードに成功したプラグイン名のリストを取得します。"""
        return list(self.plugins.keys())

    def execute_plugin(self, plugin_name: str, images: List[Image.Image], state: AppState, k: int, mask_images: List[Image.Image] = None) -> List[int]:
        """指定されたプラグイン名の classify 関数を実行します。"""
        if plugin_name not in self.plugins:
            raise ValueError(f"プラグイン '{plugin_name}' は存在しません。")
        
        func = self.plugins[plugin_name]
        
        import inspect
        sig = inspect.signature(func)
        
        # プラグイン側の関数の引数定義に応じて呼び出し方を柔軟にする
        kwargs = {}
        if 'images' in sig.parameters: kwargs['images'] = images
        if 'state' in sig.parameters: kwargs['state'] = state
        if 'k' in sig.parameters: kwargs['k'] = k
        if 'mask_images' in sig.parameters: kwargs['mask_images'] = mask_images or []
        
        logger.info(f"プラグイン実行: {plugin_name}")
        return func(**kwargs)
