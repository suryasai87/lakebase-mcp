const CLIENT_CONFIGS = {
  claude_desktop: {
    label: 'Claude Desktop',
    filename: 'claude_desktop_config.json',
    template: (url) =>
      JSON.stringify(
        { mcpServers: { lakebase: { url } } },
        null,
        2
      ),
    instructions: [
      'Open Claude Desktop Settings',
      'Navigate to Developer > MCP Servers',
      'Click "Edit Config" to open claude_desktop_config.json',
      'Add the configuration below and restart Claude Desktop',
    ],
  },
  claude_code: {
    label: 'Claude Code',
    filename: '.claude/mcp.json',
    template: (url) =>
      JSON.stringify(
        { mcpServers: { lakebase: { type: 'streamable_http', url } } },
        null,
        2
      ),
    instructions: [
      'Create or edit .claude/mcp.json in your project root',
      'Add the configuration below',
      'Claude Code will auto-detect the MCP server',
    ],
  },
  cursor: {
    label: 'Cursor',
    filename: '.cursor/mcp.json',
    template: (url) =>
      JSON.stringify(
        { mcpServers: { lakebase: { type: 'streamable-http', url } } },
        null,
        2
      ),
    instructions: [
      'Open Cursor Settings > MCP',
      'Click "Add new MCP server"',
      'Select "Streamable HTTP" transport',
      'Paste the configuration below',
    ],
  },
  vscode: {
    label: 'VS Code (Copilot)',
    filename: '.vscode/mcp.json',
    template: (url) =>
      JSON.stringify(
        { servers: { lakebase: { type: 'http', url } } },
        null,
        2
      ),
    instructions: [
      'Open or create .vscode/mcp.json in your project',
      'Add the configuration below',
      'Copilot will discover the MCP server automatically',
    ],
  },
  python_sdk: {
    label: 'Python MCP SDK',
    filename: 'client.py',
    template: (url) =>
      `from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async with streamablehttp_client("${url}") as (read, write, _):
    async with ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
        print(f"Connected! {len(tools.tools)} tools available")`,
    instructions: [
      'Install the MCP Python SDK: pip install mcp',
      'Use the code below to connect programmatically',
    ],
  },
};

export default CLIENT_CONFIGS;
