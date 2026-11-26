# Appendix I — Generative AI use disclosure

The brief allows generative AI with disclosure. We are graded on understanding the code, not on who typed it.

## Tools used

| Tool | Used for |
|---|---|
| Claude Code (Anthropic, model Claude Opus 5.5), run in the terminal inside this repository | Writing and running the pipeline scripts, SQL, charts, report templates, README and QA_PREP |
| [[TODO-HUMAN: any other tool, e.g. ChatGPT for explaining an error, Grammarly for proofreading; write "none" if none]] | |

## What we asked

- The full brief prompt is in `prompt.md`, at the repo root. It asked for the pipeline in phases, with manual steps where a human must act, beginner-readable code, and no invented data.
- Follow-up instructions during the build included:
  - "code the api so it is limited to 10k and doesnt surpass no matter what" → the YouTube quota guard in `src/utils.py`
  - approving the film list (M6)
  - confirming two fuzzy matches (M9)
  - "make the report"

## What the humans decided or changed (AI proposals that were checked or overruled)

| Step | What the AI proposed | What we decided, and why |
|---|---|---|
| M6, film list | 10 films and per-day weekend metric | Approved after reviewing the 8 dropped films and their reasons |
| M9, matching | Two matches scoring 79.1 and 90.9 | Confirmed by hand that they are the same films |
| Comment cap | The original plan said "~5,000 comments per film" | Changed to downloading all comments, because the API returns newest first |
| Trailer start time | First version used the API publish time | Corrected after finding Raid 2's comments 20.7 h before it. This weakened our own result, and we kept the weaker number |
| Bot check | First version reported "no evidence of bots" | Rewritten after the pre-publish duplicate check found Raid 2's early comments were 88.6% copy-paste |
| M10, spreadsheet | Formulas provided | [[TODO-HUMAN: did they work first time? anything you had to fix?]] |

## Our own edits (fill in before submitting)

[[TODO-HUMAN: list anything the team rewrote by hand, e.g. reflection paragraph, executive summary wording, slide titles, extra queries, and who did it]]

## How we made sure we understand it

Every member read `QA_PREP.md` (each script's 3 key lines, plus 25 viva questions) and reran `make all` once. [[TODO-HUMAN: confirm, or note who did what]]
