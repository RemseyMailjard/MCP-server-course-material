---
type: Guide
title: How to use this developer knowledge bank?
description: Practical guide to using this generic developer knowledge bank daily for work, learning, decisions and personal life.
tags: [okf, guide, knowledge-bank, developer, productivity]
timestamp: 2026-06-18T09:00:00Z
---

# How to use this developer knowledge bank?

This folder is your personal knowledge base as a developer. Each `.md` file describes one concept: a goal, project, routine, decision, learning path or personal insight.

Don't think of the bank as "a folder with documents", but as your **personal operating system** for work, growth, choices and balance.

# The core: Capture, Curate, Consult, Create

```text
1. Capture  → record quickly
2. Curate   → organize and refine
3. Consult  → review when making choices
4. Create   → use to produce output
```

- **Capture**: record tasks, insights, bugs and ideas straight into [inbox.md](inbox.md), without making them perfect.
- **Curate**: later work loose notes into clean concepts with frontmatter and clear headings.
- **Consult**: use your bank as a mirror when making choices (does this fit my goals, team, ways of working?).
- **Create**: use your knowledge as input for Copilot or ChatGPT for standups, documentation or emails.

# Recommended workflow

1. **Daily**: capture loose notes in `inbox.md`; work them out at a quiet moment.
2. **Per sprint**: update `work/current-projects.md` and `decisions/`.
3. **Weekly**: do a review with the template in `templates/weekly-review-template.md`.
4. **Per quarter**: revisit your `goals/` and `learning/learning-plan.md`.
5. **When using AI**: let an agent read the relevant files first before it produces output.

# Where do you put what?

| Situation | Where do you put it? |
|---|---|
| New task or bug | `inbox.md` or `work/current-projects.md` |
| Technical choice | `decisions/technical-decisions.md` |
| Learned something new | `learning/` |
| Insight about energy/focus | `personal/health.md` |
| Career ambition | `goals/career-growth.md` |
| 1-on-1 with your lead | `templates/one-on-one-template.md` |
| Reflection on the week | `log.md` or `personal/reflection-questions.md` |

# Minimal frontmatter

Every concept file contains at least:

```yaml
---
type: Concept
title: Title
description: Short description
tags: [tag1, tag2]
timestamp: 2026-06-18T00:00:00Z
---
```

# Tip

Use short, clear files. Ten small files are better than one large document.
