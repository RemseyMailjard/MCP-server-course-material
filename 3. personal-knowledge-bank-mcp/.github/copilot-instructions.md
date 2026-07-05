# GitHub Copilot Instructions

## Project Overview

This repository is a small Python MCP server for a developer Markdown knowledge bank. It uses FastMCP over Streamable HTTP and exposes selected files from `developer-knowledge-bank/` to MCP clients.

Primary files:

- `server.py`: FastMCP server, internal logic, tools, and prompt registration.
- `test_server.py`: pytest smoke tests for the internal server logic.
- `developer-knowledge-bank/`: Markdown knowledge source exposed by the MCP server.
- `pyproject.toml`: Python project metadata and dependencies managed by `uv`.

## Technology Choices

- Use Python 3.10+.
- Use `uv` for dependency management and command execution.
- Use FastMCP for MCP server capabilities.
- Use PyYAML for Markdown frontmatter parsing.
- Use pytest for tests.
- Keep this project lightweight; avoid adding frameworks, databases, or background services unless explicitly requested.

## Common Commands

Run these from the repository root:

```bash
uv sync
uv run server.py
uv run pytest -q
uv run fastmcp dev server.py
```

The HTTP MCP endpoint is expected at:

```text
http://127.0.0.1:8000/mcp
```

## Coding Guidelines

- Follow the existing simple module style in `server.py`.
- Keep internal logic in plain helper functions that are easy to test.
- Keep MCP tool and prompt functions thin; they should delegate to testable helpers.
- Prefer clear standard-library code over new dependencies.
- Use `pathlib.Path` for filesystem work.
- Parse YAML frontmatter through PyYAML instead of ad hoc string parsing.
- Read and write Markdown files with UTF-8 encoding.
- Return JSON-serializable values from MCP tools.
- Use descriptive function and variable names.
- Add comments only when they explain a security boundary or non-obvious behavior.

## Security Rules

The knowledge bank is a sandbox. Preserve this behavior:

- All file access must stay inside `developer-knowledge-bank/`.
- Keep using resolved paths and `Path.is_relative_to()` or an equally strong guard for path traversal protection.
- Do not allow reads outside the knowledge bank.
- Only expose Markdown files unless the user explicitly changes the project scope.
- Keep write tools constrained: `append_to_log` may only append to `log.md`, `capture_inbox_note` may only append to `inbox.md`, and template creation may only create Markdown inside the bank.
- Do not add customer data, secrets, credentials, internal URLs, or confidential material to the knowledge bank.
- Do not log sensitive file contents.

## MCP Design Guidelines

When adding MCP capabilities:

- Use tools for actions or queries that need parameters.
- Use prompts for reusable prompt templates stored in the knowledge bank.
- Use resources only when the client should browse or fetch stable content through resource URIs.
- Keep tool names clear, verb-based, and stable.
- Include concise docstrings because MCP clients surface them to users.
- Validate user input before reading files or returning content.
- Keep responses compact and predictable.

## Testing Expectations

When changing server behavior, update or add pytest coverage in `test_server.py`.

Important cases to preserve:

- Listing only Markdown files.
- Reading a known Markdown file.
- Searching content case-insensitively.
- Blocking path traversal.
- Rejecting non-Markdown or missing files.

Run `uv run pytest -q` before considering changes complete.

## Knowledge Bank Content Guidelines

Markdown files in `developer-knowledge-bank/` may use YAML frontmatter. Keep content readable by both humans and AI tools:

- Use clear headings.
- Keep frontmatter valid when present.
- Prefer stable relative links and paths.
- Keep filenames lowercase with hyphens where possible.
- Put new files in the most relevant existing folder.

## Documentation Guidelines

Update `README.md` when changing:

- Setup steps.
- Run commands.
- MCP transport or endpoint details.
- Exposed tools, prompts, or resources.
- Security assumptions.

## Avoid

- Do not bypass the sandbox helper for file access.
- Do not introduce global mutable state for request-specific behavior.
- Do not hardcode absolute machine-specific paths.
- Do not add unrelated refactors while implementing small changes.
- Do not commit changes unless the user explicitly asks.
