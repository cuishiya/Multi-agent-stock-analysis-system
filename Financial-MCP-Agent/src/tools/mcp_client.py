from langchain_mcp_adapters.client import MultiServerMCPClient
from src.utils.logging_config import setup_logger, SUCCESS_ICON, ERROR_ICON, WAIT_ICON
from src.tools.mcp_config import SERVER_CONFIGS
import asyncio

logger = setup_logger(__name__)

_mcp_client_instance = None
_mcp_tools = None
_mcp_init_lock = asyncio.Lock()


async def get_mcp_tools():
    """
    使用定义的服务器配置初始化MultiServerMCPClient，
    并从a-share-mcp-v2服务器获取可用工具。

    返回:
        list: 从MCP服务器加载的LangChain兼容工具列表。
              如果初始化或工具加载失败，则返回空列表。
    """
    global _mcp_client_instance, _mcp_tools

    if _mcp_tools is not None:
        logger.info(f"{SUCCESS_ICON} Returning cached MCP tools.")
        return _mcp_tools

    async with _mcp_init_lock:
        if _mcp_tools is not None:
            logger.info(f"{SUCCESS_ICON} Returning cached MCP tools.")
            return _mcp_tools

        logger.info(
            f"{WAIT_ICON} Initializing MultiServerMCPClient with config: {SERVER_CONFIGS}")
        try:
            candidate_client = MultiServerMCPClient(SERVER_CONFIGS)

            logger.info(
                f"{WAIT_ICON} Fetching tools from MCP server 'a_share_mcp_v2'...")
            loaded_tools = await candidate_client.get_tools()

            if not loaded_tools:
                logger.warning(
                    f"{ERROR_ICON} No tools loaded from MCP server 'a_share_mcp_v2'. Check server logs and configuration.")
                _mcp_client_instance = None
                _mcp_tools = None
                return []

            _mcp_client_instance = candidate_client
            _mcp_tools = loaded_tools
            logger.info(
                f"{SUCCESS_ICON} Successfully loaded {len(_mcp_tools)} tools from 'a_share_mcp_v2'.")
            return _mcp_tools
        except Exception as e:
            _mcp_client_instance = None
            _mcp_tools = None
            logger.error(
                f"{ERROR_ICON} Failed to initialize MCP client or load tools: {e}", exc_info=True)
            return []


async def close_mcp_client_sessions():
    """清除已缓存的 MCP 客户端与工具，允许后续重新初始化。"""
    global _mcp_client_instance, _mcp_tools

    async with _mcp_init_lock:
        if _mcp_client_instance:
            logger.info(f"{WAIT_ICON} Closing MCP client sessions...")
            logger.info(
                f"{SUCCESS_ICON} MCP client sessions (if any were persistently open) assumed closed or managed by library.")
        else:
            logger.info("MCP client was not initialized, no sessions to close.")

        _mcp_client_instance = None
        _mcp_tools = None
