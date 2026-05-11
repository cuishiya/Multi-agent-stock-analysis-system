"""
MCP服务器配置模块 - 包含连接A股MCP服务器的配置信息
"""

SERVER_CONFIGS = {
    "a_share_mcp_v2": {
        "command": "/home/ubuntu/miniconda3/envs/cui_sft/bin/python",
        "args": [
            "/home/ubuntu/桌面/cui/面向A股市场的多 Agent 协同股票分析系统/a-share-mcp-is-just-i-need/mcp_server.py"
        ],
        "transport": "stdio",
    }
}
