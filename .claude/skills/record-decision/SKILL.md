---
name: record-decision
description: Record a design decision, a new term or a roadmap change in AUTOLAB. Use when a change picks one architecture over another, reverses an earlier choice, or introduces a word the docs will keep using.
---

# Recording a decision

| what changed | where it goes |
|---|---|
| an architecture-level choice, or the reversal of one | a new ADR in `docs/adr/`, next number, the shape of the existing ones: Status with the date, Context (the options that were on the table), Decision, Consequences |
| a word people will keep using (a Stack, a tenant, a surface) | `CONTEXT.md`, and then that word everywhere, never a synonym |
| what phase the lab is in, what is next | `docs/ROADMAP.md` |
| how a concern works now | its page in `docs/gitops/`: rewritten to be true today, not appended to |
| a trap someone fell into | that page's "Things that will mislead you" |

## Steps

1. Ask whether a later reader would ask "why is it like this?". If yes, it
   is an ADR; if they would only ask "how does it work?", it is the page.
2. Write the reason and what was rejected, not the story of getting there.
   A reversed decision gets a new ADR that names the one it replaces; the
   old one's Status becomes "Superseded by ADR-NNNN".
3. Update every doc that states the old decision:
   `git grep -n -i "<the old claim>" docs/`. Done when no page contradicts
   the new one.
4. Same pull request as the change it explains.

Docs under `docs/` carry frontmatter (`tags`, `status`, `audience`); ADRs
and top-level READMEs do not.
