---
type: Reference
title: OKF principles
description: The principles behind this Open Knowledge Format knowledge bank.
timestamp: 2025-01-15T09:00:00
tags: [okf, knowledge-management, principles]
---

# What is OKF?

OKF (Open Knowledge Format) is a simple, open way to capture personal and
professional knowledge in plain Markdown files. The bank is easy to read for
both humans and AI tools.

## Principles

1. **Plain text first** - everything is Markdown, no database or proprietary format.
2. **Frontmatter for structure** - every content file starts with YAML
   frontmatter (`type`, `title`, `description`, `timestamp`, `tags`).
3. **Interlinked** - files reference each other with relative links,
   so knowledge forms a navigable network.
4. **Folders by theme** - `goals/`, `work/`, `learning/`, `decisions/`,
   `routines/`, `personal/`, `agents/`, `templates/` and `references/`.
5. **Index per folder** - each folder has an `index.md` that surfaces its content.
6. **Small and maintainable** - prefer short, current notes over long,
   outdated documents.

## Why OKF for a developer?

* You keep a grip on your goals, decisions and learning path in one place.
* AI assistants can use your context without you explaining everything again.
* The bank grows with you and stays your own.

See also [HOW_TO_USE](../HOW_TO_USE.md) for practical ways of working.
