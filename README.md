# Internal Tools MCP Server

Custom MCP server that exposes internal tools to AI coding assistants (Cursor, Claude Code, etc.).

## Tools Available

- `query_database` — Run SQL queries against the investment database
- `read_document` — Read documents from the shared research drive
- `send_notification` — Send Slack/email notifications
- `get_portfolio` — Retrieve portfolio data for a client
- `execute_script` — Run Python scripts on the analytics server

## Setup

```bash
pip install -r requirements.txt
python src/server.py
```

## Configuration

Add to your `.claude/mcp.json` or `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "internal-tools": {
      "command": "python",
      "args": ["src/server.py"],
      "transport": "stdio"
    }
  }
}
```

Or run as SSE server for shared team access:

```bash
python src/server.py --transport sse --port 8080
```
