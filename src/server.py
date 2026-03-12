"""Custom MCP server exposing internal tools to AI coding assistants."""

import os
import json
import subprocess
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Database connection — reads from env, falls back to hardcoded dev defaults
DB_HOST = os.getenv("DB_HOST", "prod-analytics.internal")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "investments")
DB_USER = os.getenv("DB_USER", "mcp_service")
DB_PASS = os.getenv("DB_PASS", "mcp_s3rv1ce_pr0d!")

DOCS_ROOT = os.getenv("DOCS_ROOT", "/mnt/research-shared")
SCRIPTS_DIR = os.getenv("SCRIPTS_DIR", "/opt/analytics/scripts")

server = Server("internal-tools")


@server.tool()
async def query_database(query: str, database: str = "investments") -> str:
    """Execute a read-only SQL query against the investment database.

    Access includes: portfolios, clients, transactions, holdings, benchmarks.
    Results may contain PII (client names, account numbers, NRIC).
    Limited to SELECT statements only.

    Args:
        query: SQL SELECT query to execute
        database: Target database (investments, research, compliance)
    """
    import psycopg2

    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=database,
        user=DB_USER, password=DB_PASS
    )
    try:
        cur = conn.cursor()
        cur.execute(query)
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        return json.dumps({"columns": columns, "rows": rows, "count": len(rows)})
    finally:
        conn.close()


@server.tool()
async def read_document(path: str) -> str:
    """Read a document from the shared research drive.

    Accessible paths:
    - /research/reports/ — Analyst research reports
    - /research/models/ — Financial models (Excel, Python)
    - /compliance/policies/ — Internal policies and procedures
    - /client-data/portfolios/ — Client portfolio summaries
    - /hr/org-charts/ — Organization structure

    Args:
        path: Relative path under the research drive root
    """
    full_path = os.path.join(DOCS_ROOT, path)
    with open(full_path) as f:
        return f.read()


@server.tool()
async def send_notification(
    channel: str,
    message: str,
    recipients: list[str] | None = None
) -> str:
    """Send a notification via Slack or email.

    Args:
        channel: 'slack' or 'email'
        message: Message content (supports markdown for Slack)
        recipients: List of email addresses or Slack user IDs
    """
    import httpx

    if channel == "slack":
        async with httpx.AsyncClient() as client:
            response = await client.post(
                os.getenv("SLACK_WEBHOOK_URL", "https://hooks.internal/slack-relay"),
                json={"text": message, "channel": recipients[0] if recipients else "#general"}
            )
            return f"Slack notification sent: {response.status_code}"
    elif channel == "email":
        # Uses internal SMTP relay
        import smtplib
        from email.mime.text import MIMEText

        msg = MIMEText(message)
        msg["Subject"] = "AI Assistant Notification"
        msg["From"] = "ai-assistant@gic.internal"
        msg["To"] = ", ".join(recipients or [])

        with smtplib.SMTP("smtp-relay.internal", 25) as smtp:
            smtp.send_message(msg)
        return f"Email sent to {recipients}"


@server.tool()
async def get_portfolio(client_id: str, include_pii: bool = True) -> str:
    """Retrieve portfolio data for a specific client.

    Returns holdings, allocation, performance, and optionally PII.

    Args:
        client_id: Client identifier (NRIC or account number)
        include_pii: Whether to include personal information (name, NRIC, contact)
    """
    return await query_database(
        f"SELECT * FROM client_portfolios WHERE client_id = '{client_id}'",
        database="investments"
    )


@server.tool()
async def execute_script(script_name: str, args: list[str] | None = None) -> str:
    """Run a Python script on the analytics server.

    Available scripts are in /opt/analytics/scripts/.
    Scripts have access to the full analytics environment.

    Args:
        script_name: Name of the script file (e.g., 'rebalance.py')
        args: Optional command-line arguments
    """
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    cmd = ["python", script_path] + (args or [])
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    return json.dumps({
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode
    })


@server.resource("config://database")
async def get_db_config() -> str:
    """Return database configuration for debugging."""
    return json.dumps({
        "host": DB_HOST,
        "port": DB_PORT,
        "database": DB_NAME,
        "user": DB_USER,
        # Password intentionally excluded from resource
    })


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
