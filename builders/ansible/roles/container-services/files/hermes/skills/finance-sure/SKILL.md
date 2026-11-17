---
name: finance-sure
description: "Answer questions about the owner's finances from Sure's API, read-only."
version: 1.0.0
author: AUTOLAB
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [Finance, Sure, Personal]
    related_skills: []
---

# Finances, from Sure

## When to use

Any question about money: balances, net worth, spending by category or
merchant, a specific transaction, loans, holdings, budgets. The source of
truth is Sure, the owner's finance app. Never guess a number; fetch it.

## How

`SURE_URL` and `SURE_API_KEY` are in the environment. The key is read-only:
every request is a GET, and a write would be refused anyway.

```sh
curl -fsS -H "X-Api-Key: $SURE_API_KEY" "$SURE_URL/api/v1/accounts"
curl -fsS -H "X-Api-Key: $SURE_API_KEY" "$SURE_URL/api/v1/transactions?per_page=100&page=1"
curl -fsS -H "X-Api-Key: $SURE_API_KEY" "$SURE_URL/api/v1/holdings"
```

Transactions are paginated and filterable (`start_date`, `end_date`,
`account_id`, `category`, `merchant`, `search`); fetch what the question needs,
not everything. Sum and group in a short Python or jq step rather than in
your head, and say which accounts and date range the answer covers.

## Rules

- Read-only. Do not try to create, update or delete anything in Sure.
- Numbers go in the reply, never into the vault unless the owner asks for a
  note. Financial detail stays out of `sources/` and `wiki/`.
- Never print the key, and never paste account numbers or full statements
  back into chat; the owner can open Sure for those.
- If Sure is unreachable, say so. Do not answer from memory.
