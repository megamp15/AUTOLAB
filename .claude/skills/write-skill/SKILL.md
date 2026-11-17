---
name: write-skill
description: Write or change an agent skill for AUTOLAB (.claude/skills). Use when a procedure keeps recurring, when a skill gave a wrong step, or when asked for a skill.
---

# Writing an AUTOLAB skill

Load the `writing-for-agents` skill first when it is installed; this adds only
what is specific to this repository.

## The contract

- **Docs hold the facts, skills hold the procedure.** What exists, why, and
  the manual steps for a person live in `docs/gitops/<concern>.md`. A skill
  says what to do in what order and points at the page. A fact written in
  both goes stale in one; move it to the page.
- **Blocks and tasks.** A *block* is one step many jobs share (dispatch a
  run, update the pages, add a secret). A *task* is a whole job (a new VM, a
  new service) and is mostly an ordered list of blocks, named in backticks so
  the agent loads them. A step that appears in two tasks becomes a block.
- **Every step ends on something checkable**: a command that exits 0, a line
  in a run's log, a status code. "Verify it works" is not a step.
- **Two sides.** Say which parts are code (a pull request, then a run) and
  which are by hand (a person in a dashboard). For the hand side the skill
  tells the agent to give the person numbered steps from the doc page with
  their real names filled in, and to say it cannot be done from here.
- **Guardrails are few and positive.** State the target ("`admins` stays in
  every list"), and keep a prohibition only where the damage is real.

## Shape of a task skill

```
---
name: <short-name>
description: <what it does>. Use when <one trigger per distinct case>.
---
# Title
One or two lines: what this covers, and the doc page that holds the facts.
## Steps            numbered; each names its block skill or its file, and its done-when
## Proof            what shows it worked, from outside
## When it goes wrong   symptom -> cause -> fix, only what was actually seen
## Guardrails
```

A block skill is the same without the task framing: when to use it, the
steps, the done-when.

## Steps

1. Name the recurring job in one line and find its doc page. No page: write
   the page first (frontmatter `tags`, `status`, `audience`; add it to
   `docs/gitops/README.md`).
2. List what the job does in order by reading the last pull request that did
   it (`git log --oneline -- <path>`), not from memory. Each item that an
   existing block covers becomes a reference to that block.
3. Write `.claude/skills/<name>/SKILL.md` in the shape above. Check every
   path, workflow input and playbook name against the repository:
   `ls .github/workflows`, the `inputs:` block of the workflow, `ls
   builders/ansible/playbooks`. Done when each one exists as written.
4. Write the description last: the leading words a person would type, one
   trigger per case, nothing the body already says.
5. Add the skill to the table below, in the same pull request.

## The skills

Blocks, called by the tasks:

| skill | the one step |
|---|---|
| `pull-request` | branch, checks, commit, PR body, merge |
| `run-workflow` | which workflow, in what order, dispatch, read the result |
| `surfaces` | home, dash and the docs agree with what is deployed |
| `secret` | a secret or variable from GitHub to the role that reads it |
| `observe` | a machine or container shows up in Grafana, alerts and home |

Tasks:

| skill | the job |
|---|---|
| `new-vm` | a machine from the map to a hardened, monitored, backed-up host |
| `service` | add, change, move or remove a container service |
| `route` | a name under `*.lab` or on the internet for something that runs |
| `pocket-id` | groups, logins, users, a refused sign-in |
| `updates` | package updates and reboots, VMs and nodes |
| `backup-restore` | back up now, prove a restore, find why a backup failed |
| `proxmox-node` | configure a hypervisor, onboard a new one, build a template |
| `nas` | the NAS's Docker projects, mounts and export rules |
| `tailnet-access` | who can reach what over Tailscale |
| `tenant` | someone else's VMs on these hypervisors |
