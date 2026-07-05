# Design Styling MCP

This repository contains a small FastMCP server that returns ready-to-use HTML, CSS, and JavaScript bundles for a compact design system. It is meant for training, prototyping, and design-oriented prompting in Copilot Chat.

The server is intentionally read-only. It exposes curated demo components, documentation, prompts, and accessibility references, but it does not create, modify, or delete files or external data.

## What is included

The server ships with:

- 4 built-in components: `button`, `card`, `feature-panel`, and `navbar`
- 6 documentation topics: `overview`, `html`, `css`, `javascript`, `accessibility`, and `composition`
- 4 token themes: `ocean`, `midnight`, `sunset`, and `forest`
- 1 file-backed MCP resource index for accessibility guidance
- 10 reusable MCP prompts for review, accessibility, and handoff workflows
- preview helpers that can return a standalone component page or a richer story page

## Tools

| Tool | Purpose |
| --- | --- |
| `list_components` | List the available demo components with id, purpose, and variant. |
| `search_components` | Search the catalog by name, purpose, notes, or layout pattern. |
| `get_component_outline` | Return the structure, notes, and suggested usage for a component. |
| `list_design_topics` | List the available documentation topics. |
| `list_resources` | List the reference-style MCP resources exposed by the server. |
| `list_prompt_templates` | List the reusable MCP prompts exposed by the server. |
| `describe_server_capabilities` | Return one compact overview of components, topics, prompts, and resources. |
| `discover_server_tools` | Return a self-describing tool catalog with examples, expected outputs, and when-to-use guidance. |
| `get_server_governance` | Return read-only boundaries, ownership, environment guidance, logging policy, and approval expectations. |
| `get_design_documentation` | Return usage guidance for a documentation topic. |
| `get_component_bundle` | Return a component's HTML, CSS, JS, notes, and outline. |
| `get_design_tokens` | Return a compact theme token set for consistent styling. |
| `build_component_page` | Generate a standalone preview page for one component. |
| `build_component_story_page` | Generate a richer review page with component, tokens, and documentation. |

## Resources and prompts

- Resource: `resource://accessibility-guidance` returns an index of five accessibility markdown guides in `resources/`.
- Prompts: the server exposes ten user-facing MCP prompts for color contrast, keyboard journeys, focus states, microcopy, theme comparison, component recommendation, and accessibility guide discovery.

Recommended discovery flow:

1. Call `discover_server_tools` if you want a self-describing catalog of the available tools and examples.
2. Call `describe_server_capabilities` for a compact overview of components, prompts, topics, and resources.
3. Call `get_server_governance` if you want the server's read-only, environment, approval, and maintainability guidance.
4. Call `list_prompt_templates` if you want to browse reusable prompt workflows.
5. Call `list_resources` if you want to inspect file-backed reference material.

## Operational safeguards

- Tool inputs are validated before component ids, topics, themes, and page titles are used.
- Error responses are structured to include the failing field, the allowed values when relevant, and a concrete next step.
- Server logging is limited to tool names and validated identifiers. It avoids logging HTML payloads, resource contents, or sensitive-looking fields.
- The current tool surface is read-only. No critical action approval flow is needed yet because the server does not expose create, update, or delete operations.

If you add a future mutating tool, keep it separate from the read tools, mark it as destructive where appropriate, and require explicit approval before release.

## Typical workflow

1. Call `list_components` or `search_components` to find the right component.
2. Use `get_component_outline` if you want a quick structural overview first.
3. Call `get_component_bundle` to retrieve the HTML, CSS, and JS bundle.
4. Optionally use `get_design_tokens` to align multiple components to the same theme.
5. Use `build_component_page` or `build_component_story_page` when you want a complete HTML preview.

## Example prompts

- "List the available demo components."
- "What can this MCP server do?"
- "Which tools are available, and can you show me examples?"
- "Show me the governance guidance for this MCP server."
- "Search for the best component for a launch story."
- "Return the feature-panel bundle with HTML, CSS, and JS."
- "Show me documentation for the accessibility topic."
- "Give me the design tokens for the sunset theme."
- "Build a preview page for the navbar component using the midnight theme."
- "Create a story page for the card component using the composition topic."

## Demo lab

Open [labs/demo-lab.html](labs/demo-lab.html) for a guided lab that explains:

- how the demo component catalog is structured
- how the token themes can be extended
- how the preview-page helpers fit into the MCP workflow

## Run it

Prerequisites:

- Python 3.11+
- `uv`

From this folder, install the environment once:

```bash
uv sync
```

Start the MCP server with the configured script entrypoint:

```bash
uv run design-mcp
```

## Run it in VS Code

Open this folder in VS Code and use the integrated terminal for the setup and run commands.

1. Open the project folder in VS Code.
2. Open a new terminal in VS Code.
3. Install the environment once:

```bash
uv sync
```

4. Start the MCP server:

```bash
uv run design-mcp
```

If you want to register the server locally in VS Code or Copilot Chat, create a local `.vscode/mcp.json` file yourself and keep it out of version control. Example:

```json
{
	"servers": {
		"design-styling-mcp": {
			"type": "stdio",
			"command": "uv",
			"args": ["run", "python", "main.py"]
		}
	}
}
```

This file is optional and is not required for the server itself. It only helps VS Code discover and start the server for local MCP usage.

What to expect:

- the server starts over `stdio`
- the terminal stays occupied while the server is running
- this is normal for an MCP server process

Stop the server with `Ctrl+C` before starting it again in the same environment.

### Windows note

On Windows, `uv run design-mcp` may fail with an access denied error for `design-mcp.exe` if an earlier server instance is still running. If that happens:

1. Stop the existing server process.
2. Run `uv run design-mcp` again.

You can also run the entrypoint directly:

```bash
uv run main.py
```

Optional environment split:

- Set `DESIGN_STYLING_MCP_ENV=development`, `test`, or `production` before starting the server if you want `get_server_governance` to report the current environment explicitly.

## Project files

- [main.py](main.py): MCP server, component catalog, documentation topics, and preview builders
- [labs/demo-lab.html](labs/demo-lab.html): guided lab for extending the demo design system
- [labs/task-1-development-standards-resource.md](labs/task-1-development-standards-resource.md): workshop assignment brief for the resource exercise
- [pyproject.toml](pyproject.toml): project metadata and script entrypoint

## Notes

The catalog is intentionally small and opinionated. The goal is to keep the output predictable and useful in demos, workshops, and lightweight frontend experiments rather than to model a full production design system.