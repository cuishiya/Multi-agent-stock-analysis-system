"""项目运行时环境变量适配。"""

import os
from collections.abc import MutableMapping


DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-v4-flash"


def configure_deepseek_environment(
    environment: MutableMapping[str, str] | None = None,
) -> bool:
    """将系统 DeepSeek 密钥映射为项目现有的 OpenAI-compatible 配置。"""
    target = os.environ if environment is None else environment
    api_key = target.get("DeepSeek_API_KEY") or target.get("DEEPSEEK_API_KEY")
    if not api_key:
        return False

    target["OPENAI_COMPATIBLE_API_KEY"] = api_key
    target["OPENAI_COMPATIBLE_BASE_URL"] = DEEPSEEK_BASE_URL
    target["OPENAI_COMPATIBLE_MODEL"] = DEEPSEEK_MODEL
    target["SUMMARY_USE_LOCAL_MODEL"] = "api"
    target["USE_LOCAL_MODEL"] = "api"
    return True
