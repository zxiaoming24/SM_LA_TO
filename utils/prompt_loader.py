import os
import json
from typing import Dict, Any, Optional


class PromptLoader:
    """
    提示词加载器，用于从文件中加载提示词模板
    """

    def __init__(self, base_dir: str = "prompts"):
        """
        初始化提示词加载器

        Args:
            base_dir: 提示词文件的基础目录
        """
        self.base_dir = base_dir
        self._ensure_directory_exists()

    def _ensure_directory_exists(self):
        """确保提示词目录存在"""
        os.makedirs(self.base_dir, exist_ok=True)

    def _validate_filename(self, filename: str) -> str:
        """校验文件名安全性，防止路径穿越攻击"""
        # 拒绝包含路径分隔符或穿越字符的文件名
        if os.sep in filename or os.altsep and os.altsep in filename:
            raise ValueError(f"非法的文件名（不允许路径分隔符）: {filename!r}")
        if '..' in filename:
            raise ValueError(f"非法的文件名（不允许路径穿越）: {filename!r}")
        file_path = os.path.normpath(os.path.join(self.base_dir, filename))
        if not file_path.startswith(os.path.normpath(os.path.abspath(self.base_dir)) + os.sep):
            raise ValueError(f"文件名解析后超出基础目录: {filename!r}")
        return file_path

    def load_prompt(self, filename: str) -> str:
        """
        从文件加载提示词

        Args:
            filename: 提示词文件名（包含扩展名）

        Returns:
            str: 提示词内容

        Raises:
            FileNotFoundError: 如果文件不存在
        """
        file_path = self._validate_filename(filename)

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"提示词文件不存在: {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except Exception as e:
            raise Exception(f"读取提示词文件失败: {e}")

    def load_prompt_with_defaults(self, filename: str, defaults: Dict[str, Any] = None) -> str:
        """
        加载提示词，如果文件不存在则使用默认内容

        Args:
            filename: 提示词文件名
            defaults: 默认提示词内容

        Returns:
            str: 提示词内容
        """
        try:
            return self.load_prompt(filename)
        except FileNotFoundError:
            if defaults and filename in defaults:
                return defaults[filename]
            raise

    def save_prompt(self, filename: str, content: str):
        """
        保存提示词到文件

        Args:
            filename: 文件名
            content: 提示词内容
        """
        file_path = self._validate_filename(filename)
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content.strip())
            print(f"提示词已保存到: {file_path}")
        except Exception as e:
            raise Exception(f"保存提示词失败: {e}")

    def get_all_prompts(self) -> Dict[str, str]:
        """
        获取所有提示词文件及其内容

        Returns:
            Dict[str, str]: 文件名到内容的映射
        """
        prompts = {}
        for filename in os.listdir(self.base_dir):
            if filename.endswith(('.txt', '.prompt', '.md')):
                try:
                    prompts[filename] = self.load_prompt(filename)
                except Exception as e:
                    print(f"加载提示词文件 {filename} 失败: {e}")
        return prompts