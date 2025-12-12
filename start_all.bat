@echo off
chcp 65001 >nul 2>&1
echo Starting system...
echo.

echo [1/2] Starting MCP server...
start "MCP Server" cmd /k "python -m mcp_server.http_server"
ping 127.0.0.1 -n 4 >nul

echo [2/2] Starting AI agent...
echo.
python -m agent.agent

pause