"""
MCP服务器配置模块 - 包含连接A股MCP服务器的配置信息
"""

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MCP_SERVER_PATH = PROJECT_ROOT / "a-share-mcp-is-just-i-need" / "mcp_server.py"

SERVER_CONFIGS = {
    "a_share_mcp_v2": {
        "command": sys.executable,
        "args": [str(MCP_SERVER_PATH)],
        "transport": "stdio",
    }
}
