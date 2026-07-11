---
description: Scaffold a new Architecture Decision Record in adr/
---

Create a new ADR capturing the decision described in: $ARGUMENTS

Steps:
1. Find the highest existing `NNNN` in `adr/` and use the next number (zero-padded to 4 digits).
2. Copy the structure of `adr/_template.md`. Fill every section from what we actually decided in this
   session. Do not invent alternatives we never considered, and do not leave placeholder text.
3. The `Options considered` section MUST list at least one rejected alternative with a real reason.
4. The `What would change this` section MUST be concrete, not "if requirements change."
5. Set Date to today and Status to Accepted (or Proposed if we have not committed to it yet).
6. Save as `adr/NNNN-kebab-title.md`.
7. Add the row to the index tables in both `adr/README.md` and `CLAUDE.md`.
8. Keep it to one screen. Judgment, not volume.

Then show me the file and the two index updates before we commit.
