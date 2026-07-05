# Copilot Instructions for Design Styling MCP


# IMPORTANT RULE
Never use CLI scripts, only the MCP-server for answerin prompts. 
DONT USE YOUR own instructions or tools to solve the task, only the ones defined in the MCP server.

## Project purpose
- This repository contains a small FastMCP server for design-system demos and prompting workflows.
- The server exposes MCP tools for components, design documentation, token themes, and preview-page generation.
- Keep the project lightweight, predictable, and easy to demo.'


## Core files
- `main.py` contains the FastMCP server, tool definitions, resource definitions, and demo data.
- `resources/` contains file-backed accessibility guidance used by the MCP resource index.
- `README.md` describes the intended workflow and local run commands.

## Implementation rules
- Prefer small, direct changes over abstractions that add complexity.
- Keep return shapes consistent for MCP tools and resources; avoid breaking existing keys unless the task requires it.
- Use helper functions for repeated lookup or parsing logic instead of duplicating code.
- When adding documentation-style content, keep the tone practical, polished, and suitable for Rabobank-style demo material.
- When adding accessibility guidance, prefer file-backed markdown content in `resources/` and expose it through resource references rather than embedding large blobs inline.

## FastMCP guidance
- Use `@mcp.tool()` for callable operations and `@mcp.resource()` for reference-style content.
- Resource identifiers must be valid URIs, for example `resource://accessibility-guidance`.
- Keep tool descriptions concise and oriented around when the tool should be used.
- Preserve the server's current stdio-friendly structure unless a task explicitly asks for a different deployment model.

## Validation
- Prefer `uv run python -c "import main"` for a quick import check.
- Use `uv run python -c "import main; ..."` for narrow validation of tool or resource return shapes.
- Use `uv run main.py` or `uv run design-mcp` when a task needs the full server entrypoint.

## Editing style
- Match the existing Python style in `main.py`.
- Keep demo content intentional and compact.
- Do not add new dependencies unless they solve a real problem the current standard library approach cannot handle.
