"""
ResQAI - MCP Client Registry
Centralized access point for all MCP servers.
Agents call MCP tools through this client rather than directly.
"""

from typing import Optional
from loguru import logger


class MCPClient:
    """
    Central registry for all MCP server instances.
    Provides a unified interface for agents to call MCP tools.
    Handles lazy initialization and error isolation.
    """

    def __init__(self) -> None:
        self._maps: Optional[object] = None
        self._weather: Optional[object] = None
        self._fssai: Optional[object] = None

    @property
    def maps(self):
        """Google Maps MCP server."""
        if self._maps is None:
            from app.mcp.servers.maps_server import MapsMCPServer
            self._maps = MapsMCPServer()
        return self._maps

    @property
    def weather(self):
        """OpenWeatherMap MCP server."""
        if self._weather is None:
            from app.mcp.servers.weather_server import WeatherMCPServer
            self._weather = WeatherMCPServer()
        return self._weather

    @property
    def fssai(self):
        """FSSAI MCP server."""
        if self._fssai is None:
            from app.mcp.servers.fssai_server import FSSAIMCPServer
            self._fssai = FSSAIMCPServer()
        return self._fssai

    async def call(self, server: str, tool: str, **kwargs) -> Optional[dict]:
        """
        Generic MCP tool invocation.

        Args:
            server: MCP server name (maps, weather, fssai)
            tool: Tool/method name
            **kwargs: Tool arguments

        Returns:
            Tool result or None on failure
        """
        try:
            server_instance = getattr(self, server, None)
            if not server_instance:
                logger.warning(f"MCP server '{server}' not found")
                return None

            method = getattr(server_instance, tool, None)
            if not method:
                logger.warning(f"MCP tool '{server}.{tool}' not found")
                return None

            result = await method(**kwargs)
            logger.debug(f"MCP call success: {server}.{tool}")
            return result

        except Exception as e:
            logger.error(f"MCP call failed {server}.{tool}: {e}")
            return None


# Module-level singleton
_mcp_client: Optional[MCPClient] = None


def get_mcp_client() -> MCPClient:
    """Get the global MCP client instance."""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClient()
    return _mcp_client
