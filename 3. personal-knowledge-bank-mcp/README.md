# Developer Knowledge Bank — MCP server

A small, runnable example of a generic knowledge bank for a Rabobank developer
employee. It exposes a folder of Markdown notes (`developer-knowledge-bank/`),
covering work and personal life, to an AI assistant through an HTTP MCP server
built with [FastMCP](https://gofastmcp.com), managed with
[uv](https://docs.astral.sh/uv/).

The server offers read tools, metadata search, OKF validation, link/navigation
helpers, workflow prompts, a resource template and constrained write tools for
logs, inbox captures and template-based note creation:

| Surface | Name | What it does |
| --- | --- | --- |
| Tool | `list_knowledge_files` | Lists every Markdown file in the bank. |
| Tool | `read_knowledge_file` | Reads one file (sandboxed to the bank). |
| Tool | `search_knowledge_bank` | Searches titles, tags and content. |
| Tool | `get_knowledge_map` | Groups notes by folder with frontmatter metadata. |
| Tool | `list_knowledge_tags` | Lists unique frontmatter tags. |
| Tool | `list_knowledge_types` | Lists unique frontmatter type values. |
| Tool | `search_knowledge_metadata` | Searches file paths and frontmatter metadata. |
| Tool | `validate_knowledge_bank` | Checks OKF frontmatter, duplicate titles and local Markdown links. |
| Tool | `find_stale_notes` | Finds notes older than a timestamp threshold. |
| Tool | `find_placeholder_text` | Finds unfinished TODO/TBD/template placeholder lines. |
| Tool | `validate_index_coverage` | Checks that folder indexes link to their notes. |
| Tool | `list_outgoing_links` | Lists Markdown links from one note and whether targets exist. |
| Tool | `find_backlinks` | Finds notes that link to a given note. |
| Tool | `find_orphan_notes` | Finds notes that no other note links to. |
| Tool | `find_related_notes` | Finds notes related by links, backlinks or shared tags. |
| Tool | `prepare_project_context` | Returns tasks, team, ways of working and tech stack for the current project. |
| Tool | `prepare_technical_decision_context` | Returns technical-decision, ways-of-working, secure-coding and template notes. |
| Tool | `prepare_growth_context` | Returns career-growth, skills, learning-plan and career-decision notes. |
| Tool | `prepare_learning_context` | Returns the learning template, plan, tech stack and matching topic notes. |
| Tool | `prepare_goal_alignment_context` | Returns goals, values, decisions and routine context for goal fit. |
| Tool | `check_goal_alignment` | Returns evidence signals for how a proposal overlaps with saved goals and rules. |
| Tool | `list_recent_notes` | Lists notes ordered by frontmatter timestamp. |
| Tool | `get_daily_briefing_context` | Returns daily briefing context and recent notes. |
| Tool | `get_weekly_review_context` | Returns weekly-review context and recent notes. |
| Tool | `append_to_log` | Appends a dated entry to `log.md`. |
| Tool | `capture_inbox_note` | Appends a raw capture to `inbox.md` for later curation. |
| Tool | `create_note_from_template` | Creates a Markdown note from an existing template. |
| Tool | `list_templates` | Lists templates available for safe note creation. |
| Tool | `preview_note_from_template` | Previews generated Markdown without writing a file. |
| Tool | `create_learning_note` | Creates a learning note from the learning-note template. |
| Tool | `create_project_note` | Creates a project brief note from the project brief template. |
| Tool | `create_decision_note` | Creates a decision note from the decision template. |
| Resource template | `knowledge://{path}` | Reads Markdown files as MCP resources. |
| Prompt | `standup_update` | Surfaces the saved standup prompt. |
| Prompt | `weekly_review` | Starts a weekly review workflow. |
| Prompt | `learning_design` | Starts a focused learning-note workflow. |
| Prompt | `one_on_one_prep` | Prepares a 1-on-1 with your lead. |
| Prompt | `project_kickoff` | Starts a new-project preparation workflow. |

Every file access goes through a **path-traversal guard**: a request like
`../../etc/passwd` is rejected before any file is opened.

## Project layout

```
developer-knowledge-bank-mcp/
├── pyproject.toml             # project metadata + dependencies
├── server.py                  # FastMCP server, tools, prompts and helpers
├── test_server.py             # pytest smoke tests for internal logic
├── README.md
└── developer-knowledge-bank/  # the knowledge bank itself
    ├── HOW_TO_USE.md
    ├── index.md
    ├── inbox.md
    ├── log.md
    ├── agents/                # assistant instructions and prompt notes
    ├── decisions/             # technical and career decision records
    ├── goals/                 # career, skills, balance and health goals
    ├── learning/              # learning plan and topic notes
    ├── personal/              # values, health, finances, hobbies, reflection
    ├── references/            # OKF principles and reference notes
    ├── routines/              # daily, sprint and weekly-review routines
    ├── templates/             # safe note-creation templates
    └── work/                  # projects, team, tech stack and ways of working
```

## Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/) installed.
  (uv manages Python and all dependencies for you — no manual `pip` needed.)

## Install

From the project folder:

```bash
uv sync
```

This creates an isolated `.venv` and installs FastMCP from `pyproject.toml`,
pinning exact versions in `uv.lock`.

## Run

```bash
uv run server.py
```

The server starts on **Streamable HTTP** at:

```text
http://127.0.0.1:8000/mcp
```

It will keep running while it waits for MCP clients. Stop it with `Ctrl+C`.

## Test the logic

```bash
uv run python -m pytest -q
```

## Knowledge workflows

The tools are designed around a few common MCP workflows:

- **Orient first:** use `get_knowledge_map`, `list_knowledge_tags`,
  `list_knowledge_types` or `search_knowledge_metadata` before reading many
  full Markdown files.
- **Validate quality:** use `validate_knowledge_bank`,
  `validate_index_coverage`, `find_stale_notes` and `find_placeholder_text` to
  keep the OKF notes structured, linked and current.
- **Navigate relationships:** use `list_outgoing_links`, `find_backlinks`,
  `find_related_notes` and `find_orphan_notes` to improve discoverability.
- **Prepare context:** use the `prepare_*_context` tools and briefing tools for
  project work, technical decisions, growth, learning and weekly review.
- **Write safely:** use `append_to_log`, `capture_inbox_note`,
  `preview_note_from_template` and the template creation tools instead of
  arbitrary file writes.

## Try it interactively (MCP Inspector)

FastMCP ships a dev inspector:

```bash
uv run fastmcp dev server.py
```

Then call tools such as `list_knowledge_files`, `search_knowledge_metadata`,
`get_knowledge_map`, `validate_knowledge_bank`, `validate_index_coverage`,
`find_placeholder_text`, `find_related_notes`, `get_daily_briefing_context`,
`preview_note_from_template` and `prepare_learning_context` from the Inspector UI.

You can also run the HTTP server and connect an MCP client to
`http://127.0.0.1:8000/mcp`.

## Connect to Claude Desktop

This example now runs as HTTP. For local-only Claude Desktop usage, the old
stdio transport is usually simpler because the desktop app can start and stop
the server process for you. HTTP is a better fit when you want a long-running
server URL, a tunnel, or a remote deployment.

For HTTP, run the server and connect an MCP client that supports Streamable HTTP
to `http://127.0.0.1:8000/mcp`. If you want Claude Desktop to launch this as a
local process, use the stdio version instead.

Restart Claude Desktop and ask, for example:

- *Which files are available in my knowledge bank?*
- *Read my current projects.*
- *Search my knowledge bank for OKF.*
- *Based on my knowledge bank, what are my current goals?*
- *Validate my knowledge bank and show the most important cleanup items.*
- *Find stale notes older than 90 days.*
- *Find placeholder text that still needs curation.*
- *Check whether my folder indexes link to all notes.*
- *Which notes link to my learning plan?*
- *Find orphan notes that need more links.*
- *Does this side project fit my goals and work-life balance?*
- *Give me a daily briefing from my current project, goals, routines and log.*
- *Prepare learning context for Azure AI.*
- *Prepare technical-decision context for choosing a message queue.*
- *Capture this raw idea in my inbox: try trunk-based development next sprint.*
- *Preview a new decision note from the decision template.*
- *Create a new learning note from the learning-note template.*

## Security note

This bank deliberately contains **no** customer data, secrets, real colleague
names or internal URLs. The folder root is treated as a hard sandbox. Read tools
only read `.md` files inside it, `append_to_log` can only append to `log.md`,
`capture_inbox_note` can only append to `inbox.md`, and template creation tools
can only create or overwrite `.md` files inside the bank when explicitly asked.
Keep it that way: see Module 9 of the course reader for the data-classification
reasoning.
