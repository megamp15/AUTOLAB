---
name: finance-upkeep
description: Run the recurring finance upkeep against the deployed Sure - link transfers, split loan payments, review categories, add Dasond months. Use when asked for finance upkeep, after new statements are loaded, or about monthly.
---

# Finance upkeep

Everything about what it changes and why is in
`apps/local-finance-backfill/upkeep/README.md`. Read it first: the rules
there are the owner's decisions about their own money.

## Steps

1. Dry run, from `apps/local-finance-backfill/upkeep`:

   ```
   ./run.sh
   ```

   It needs the lab tailnet and SSH as `gitops@nebula`. If it cannot reach
   nebula, this machine is on another Tailscale profile: stop and say so.
2. Tell the owner, in plain words, what it would change and every `REVIEW`
   line: pending matches that do not look like a payment, Nelnet debits
   waiting on a statement, the classifier's guesses, anything uncategorized.
3. On their go: `./run.sh --write`. It backs up Sure's database first.
4. Work through the `REVIEW` lines with the owner. A category that will
   repeat becomes a rule; a wrong guess is corrected and locked (the README
   has both).
5. Done when a second dry run lists nothing it would change, and only the
   `REVIEW` lines the owner chose to leave.

`SINCE=<ISO time> ./run.sh` widens the window for classifier guesses.
New Dasond months and pay stubs: the README's "Dasond" section.

## Guardrails

- Never `--write` before the owner has seen the dry run.
- Amounts, payees and balances stay out of pull requests, commit messages
  and any note that leaves this machine.
