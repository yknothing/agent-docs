---
name: vendor-onboarding
description: >-
  STAGE 2 PLACEHOLDER. Documents the future skill for adding a new vendor docs
  library (OpenAI / Gemini / Cursor / ...) to agent-docs. NOT YET ACTIVE.
  Stage 1 only supports `anthropic` (active); other vendors are `reserved` in
  agent_docs/vendors/registry.py.
---

# Vendor Onboarding (Stage 2 — Placeholder)

> **Status:** PLANNED. This skill is referenced by `workflows/stage1_source_library.md`
> and `ARCHITECTURE.md` as the future entry point for adding a new vendor.
> It is **NOT** active in Stage 1. Do not invoke it; if a user asks to add a
> new vendor, escalate by pointing them at this file and the open question below.

## Why this file exists (instead of an empty folder)

Previously, `ARCHITECTURE.md` and `workflows/stage1_source_library.md` referenced
`skills/vendor-onboarding/` as if it existed. To avoid Agent confusion ("file
referenced but missing"), this placeholder pins the intent and the open design
questions until Stage 2 begins.

## What this skill MUST cover (when implemented)

When Stage 2 starts, this skill should walk the operator through:

1. **Source inventory**: official documentation roots, blog/news sources,
   sitemap or `llms.txt` equivalent, RSS, language editions.
2. **URL → folder mapping rule** (extends `feishu_folder_segments`): host,
   path-locale stripping, category map (`learn` → "Academy" etc.),
   skipped paths (video courses, search, login).
3. **Vendor adapter contract**: how `agent_docs/vendors/<vendor>.{toml,py}`
   declares hosts, locales, category map, artifact root.
4. **QA samples**: at least 3 sample URLs whose `final.zh.md` / `final.en.md`
   pass `technical + content QA` end-to-end.
5. **Cutover checklist**: registry status `reserved` → `active`, add CI
   smoke pointing at the new vendor, update `README.md` vendor table.
6. **Anti-checklist** (what NOT to do):
   - Do NOT copy `scripts/anthropic_content_pipeline.py` per-vendor.
   - Do NOT hardcode vendor mapping in `feishu_folder_segments` with another
     `elif host == "...":` branch — the mapping logic should be data-driven
     by then.

## Open design question (Stage 2 must resolve)

The Stage 1 mapper hardcodes vendor branches in `sinks/feishu.py`. Before
Stage 2 onboarding can be repeatable, this must become **data-driven** (vendor
config file or `agent_docs/vendors/<vendor>/adapter.py`). See ARCHITECTURE.md
"Known Limitations" entry on multi-vendor scaling.

## Until then

If a user asks: *“can you add OpenAI docs now?”* — the answer is **no, Stage 2
is not started; only `anthropic` is `active`**. Vendor registry entries for
`openai` / `gemini` / `cursor` exist only to reserve filesystem and Feishu
folder names; they do not have crawl pipelines.

## References

- `agent_docs/vendors/registry.py` — current vendor states
- `ARCHITECTURE.md` — vendor onboarding checklist (informational)
- `workflows/stage1_source_library.md` — Stage 1 boundary
