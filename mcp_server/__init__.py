"""MCP Server для управления складом и запасами."""

from .mcp_tools import mcp
from .http_server import app

__version__ = "1.0.0"
__all__ = ["mcp", "app"]