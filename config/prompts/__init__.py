"""
Prompt 管理模块
从 markdown 文件加载 LLM prompts
"""

from pathlib import Path

# Prompt 文件目录
PROMPTS_DIR = Path(__file__).parent


def load_prompt(name: str) -> str:
    """
    加载指定名称的 prompt 文件

    Args:
        name: prompt 文件名（不含扩展名），如 'stage1_classifier'

    Returns:
        prompt 内容字符串
    """
    file_path = PROMPTS_DIR / f"{name}.md"
    if not file_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


# 预加载常用 prompts
_cache = {}


def get_stage1_prompt() -> str:
    """获取 Stage 1 分类器的 system prompt"""
    if "stage1" not in _cache:
        _cache["stage1"] = load_prompt("stage1_classifier")
    return _cache["stage1"]


def get_stage2_prompt() -> str:
    """获取 Stage 2 分析器的 system prompt"""
    if "stage2" not in _cache:
        _cache["stage2"] = load_prompt("stage2_analyzer")
    return _cache["stage2"]
