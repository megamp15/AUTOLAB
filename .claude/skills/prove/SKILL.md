---
name: prove
description: Prove an AUTOLAB change works by trying to break it - an alert that has fired, a login that was refused, a backup that booted. Use at the end of any change that claims to protect, alert, restrict or recover.
---

# Prove it by breaking it

A green run says the playbook finished. It does not say the thing works.
The lab's rule: a claim is done when its failure has been caused on purpose
and seen to be caught. Record what was done and what was seen, in the pull
request or the doc page's proofs table, with the times.

## The proof for each kind of claim

| the claim | break it like this | it holds when |
|---|---|---|
| a page needs a login | `curl` it signed out, then with a forged session cookie, then a write with no login | 401 each time, and the app's own log shows no request arrived |
| only one group opens it | sign in as a user outside the group | 403, the app never answered |
| it is not public | resolve and fetch the name from off the tailnet (a phone on cellular) | no answer |
| it is public | the same phone | it opens |
| an alert pages | cause the condition: stop the agent, the container, the tunnel | `pending`, then `firing`, the notification on the phone, then cleared after undoing it |
| a threshold alert pages | lower the threshold for one run rather than filling a disk | the same, then restore the number |
| a backup is good | restore it: `09` in `test` mode | `BOOTED as <os>` in the run summary |
| a database dump is good | the restore test into a scratch container | the same table count as production |
| a firewall rule is tight | connect from a source the rule does not name | refused |
| a port is tailnet-only | connect to the host's LAN address on that port | refused |
| a token gate works | request the backend directly, without Traefik's header | 403 |
| a rerun is safe | run the playbook a second time | `changed=0` |

## Steps

1. Write the claim as one sentence that could be false.
2. Pick the row. Say what you are about to break and what will be down
   while you do, and get the user's go for anything that pages them or
   takes a service down.
3. Break it, watch it get caught, undo it, watch it clear.
4. Write down what you did and saw. What only the user can do (a passkey
   tap, a phone on cellular) is handed to them as steps, and stays listed
   as not yet proven until they say what they saw.

## Guardrails

- One break at a time, undone before the next.
- Never test a destructive path on the only copy: a restore test goes to a
  new guest, a replace is not a test.
