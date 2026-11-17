---
name: secret
description: Add, rotate or remove a GitHub secret or variable that an AUTOLAB workflow or role reads. Use when a service needs a token, password, key or a per-deployment value.
---

# A secret or a variable

The full list and what reads each is
`docs/gitops/github-secrets-variables-reference.md`.

## Decide

- **Secret or variable.** A value that grants something is a secret. A name,
  an address or a URL is a variable. The tailnet's domain is a secret
  (`TAILNET_DOMAIN`) because the repository is public.
- **Repository or environment.** Repository-level by default. Environment
  (`lab`, `edge`, `qnta`) when Stacks need different values: an environment
  value shadows the repository's of the same name.
- **Or neither.** A secret that only matters next to the data it protects
  (a database password, a cookie key, a token between two containers) is
  generated on the host on the first run and kept under `/etc/autolab/`. It
  never goes to GitHub. Most service secrets are this kind.

## Steps

1. Get the value without seeing it when you can: ask for it through the
   harness's secret request, or have the user run `gh secret set NAME`
   themselves. A value pasted into chat is in the transcript.
2. Set it: `gh secret set NAME --env lab` or `gh variable set NAME --body '<value>'`.
3. Wire it, all four places, or the role never receives it:
   - the job's `env:` block in `.github/workflows/05_ansible-builder.yml`
     (`AUTOLAB_<NAME>: ${{ secrets.NAME }}`), limited to the playbook that
     needs it;
   - the Python map in the same file that renders the extra-vars file
     (`"autolab_<role>_<name>": os.environ.get("AUTOLAB_<NAME>", "")`);
   - the role's `defaults/main.yml`, empty, with a comment saying what it is
     and where it comes from;
   - a row in the reference doc.
4. In the role, refuse to run when a required one is empty, by name: an
   `assert` whose message says which GitHub secret is missing. Mark tasks
   that handle it `no_log: true`.
5. Done when a check-mode run of the playbook passes, and its log shows the
   name and never the value.

## Rotate, remove

Rotate: set the new value, run the playbook that reads it. Remove: all four
places in step 3, then `gh secret delete NAME`.
