# Icarus Claude Code Plugin — Next-Session Handoff

**Prepared:** 2026-08-14  
**Next session goal:** package Icarus's already-shipped MCP connector as a
Figma-style Claude Code plugin with focused skills and evals. Do not build a
second MCP server or change the brain.

## 1. Alankrit's explicit operating instruction

Do not change `.gitlab-ci.yml`, CI/CD behavior, signing policy, Azure deployment
behavior, or any other deployment pipeline unless Alankrit explicitly approves
that exact change first. Explain proposed pipeline/deployment changes before
making them.

This instruction was reinforced after the universal connector commit added a
stable-signing requirement to `package_dmg.sh` without prior discussion. That
guard has been reverted. Ad-hoc GitLab DMG packaging is the accepted current
alpha release model.

## 2. Product truth for this task

Icarus is a privacy-first conversational engineering brain. Its coding-agent
surface retrieves recorded engineering context and returns cited evidence or an
honest unknown. It is not a generic autonomous coding agent.

The Claude Code connector is already production code:

- `/Applications/Icarus.app/Contents/MacOS/Icarus --mcp` is a dependency-free
  stdio MCP server inside the installed app.
- The installer registers it as the user-scoped `icarus` server when Claude
  Code is present.
- Icarus Settings diagnoses, installs, and repairs that registration by calling
  Claude's CLI; it does not edit Claude configuration files directly.
- The app keeps the GitHub bearer in Keychain and exchanges it for a ten-minute,
  in-memory, repository-bound, read-only agent session. Claude never receives
  the GitHub credential.
- Repository mismatches fail closed. The adapter cannot switch repositories or
  edit code.

Current MCP tools:

1. `get_change_context(repo, question)`
2. `explain_code_context(repo, path, start, end, question?)`
3. `get_task_context(repo, task)`

Canonical implementation:

- `mac/Icarus/Sources/Icarus/McpCommand.swift`
- `mac/Icarus/Sources/Icarus/ClaudeConnector.swift`
- `mac/Icarus/Sources/IcarusKit/McpServer.swift`
- `mac/Icarus/Sources/IcarusKit/McpContract.swift`
- `.mcp.json`
- `site/install.sh`

`docs/BUILD_ORDER.md` already records Phase 1B distribution as complete. The
next task is a discoverability/workflow packaging layer, not a new capability.

## 3. Verified production state at handoff

- GitLab `main`: `5f41f7086c8b029d7dc8a0e17a243a6048f33b3f`
- Universal Mac MCP connector: `a2ca6bafa821f2462d78da865f78c268b81993b7`
- Ad-hoc packaging restoration: `49000252e0cf31c9113c2e51102c4a84c7e3a1c4`
- Version release: Icarus `0.1.7`, build `10`
- Release metadata commit: `5f41f70`
- Public site: <https://icarus-website-kappa.vercel.app>
- Live DMG SHA-256:
  `c4d2837c847135823bd310a99f2662c71d957787d9b14490f97d8d33a69ec76e`
- Live Sparkle appcast advertises `0.1.7` / build `10`; its EdDSA signature was
  verified against the live DMG.
- GitLab packaging pipeline #46 passed and produced the ad-hoc DMG.
- Release-metadata pipeline #47 passed.
- Azure stayed healthy on revision `icarus-brain--0000064`, image
  `icarus-brain:a2ca6baf`. The later commits changed only Mac packaging/version
  and site metadata, so no redundant brain deploy was created.
- The Homebrew cask was not updated during the website-only publication.

## 4. What “Figma-style connector” means for Icarus

Figma's Claude integration combines an MCP server with plugin installation and
workflow skills. Icarus already has the MCP server. Add only:

```text
icarus Claude plugin
├── .claude-plugin/plugin.json
├── .mcp.json
├── skills/
│   └── using-icarus-engineering-memory/SKILL.md
└── evals/
```

The plugin MCP configuration must launch the installed app:

```json
{
  "mcpServers": {
    "icarus": {
      "type": "stdio",
      "command": "/Applications/Icarus.app/Contents/MacOS/Icarus",
      "args": ["--mcp"]
    }
  }
}
```

The plugin must not copy the brain, embed credentials, add an API key, or
replace the Mac app. The Mac app remains the trust and credential bridge.

## 5. Skill behavior to package

The skill should make Claude consult Icarus on observable events, matching the
measured trigger language already generated into `McpContract.swift`:

- before editing or patching a file;
- before opening a pull request;
- before concluding a reported bug is already fixed;
- before stating that current behavior is intentional;
- use `explain_code_context` when exact lines are involved;
- use `get_task_context` for a real multi-file task;
- use `get_change_context` for one focused historical question.

The skill must also teach response discipline:

- citations prove that retrieved sources exist, not that every composed
  sentence is necessarily entailed;
- verify `composed` claims against the repository before relying on them;
- `rests_on_rejected: true` means the cited evidence does not prove the change
  landed;
- a closed unmerged pull request is evidence that someone tried something, not
  evidence of why it was closed;
- preserve honest unknowns and never promote related evidence into a recorded
  decision.

Keep the skill concise. Do not duplicate the very long tool descriptions. The
MCP contract remains the capability and safety source of truth.

## 6. Next-session execution checklist

1. Read `AGENTS.md`, `CODEX.md`, `general_index.md`, `docs/VISION.md`,
   `docs/WORKFLOWS.md`, this handoff, and the implementation files listed above.
2. Run `git status`. The working tree is intentionally dirty with unrelated
   user-owned work. Preserve it. In particular, `plugins/` already contains
   untracked Ponytail material; inspect before choosing a plugin path and never
   stage it accidentally.
3. Confirm the installed Claude CLI's current plugin schema using
   `claude plugin init --help` and a disposable scaffold. Current observed CLI:
   Claude Code `2.1.227`; it supports `--with skills mcp`, strict validation,
   plugin evals, marketplaces, and local plugin loading.
4. Create the smallest Icarus plugin in an isolated path. Recommended initial
   name: `icarus`; recommended skill name:
   `using-icarus-engineering-memory`.
5. Point the plugin MCP entry only at the installed app binary and `--mcp`.
6. Add the concise trigger/interpretation skill described in §5.
7. Add plugin evals before polishing distribution. At minimum cover:
   - edit/patch trigger;
   - pull-request trigger;
   - “already fixed” trigger;
   - “intentional behavior” trigger;
   - no call for an unrelated trivial request;
   - honest handling of unknown, `composed`, and `rests_on_rejected` output.
8. Validate with `claude plugin validate --strict <plugin-path>`.
9. Test in a fresh Claude Code session against the installed Icarus `0.1.7`:
   the server must initialize, list exactly the three existing tools, return an
   actionable signed-out error, fail closed on a repository mismatch, and
   return cited context for the connected repository.
10. Measure actual MCP calls from Claude transcripts with
    `scripts/agent_call_audit.py`; do not rely on Claude's self-report. Compare
    a no-plugin baseline with the plugin arm where practical.
11. Run proportionate existing Swift/Python verification. Do not weaken the MCP
    contract, honesty gates, or their tests to make plugin evals pass.
12. Report results and remaining risks before any public marketplace
    publication. Adding a public marketplace/repository is an external
    distribution action and requires Alankrit's explicit approval.

## 7. Definition of done for the next brick

- A locally installable Icarus Claude plugin validates strictly.
- A fresh Claude Code session discovers the plugin and the existing three Icarus
  MCP tools without a checkout-specific Python dependency.
- The skill causes consultation on the four measured observable events without
  claiming unsupported capabilities.
- Credentials remain absent from Claude/plugin configuration.
- Existing connector, honesty, privacy, and repository-mismatch tests remain
  green.
- No CI/CD, Azure, signing, release, or deployment configuration changes are
  made without explicit prior approval.
- No public marketplace publication occurs without explicit approval.

## 8. Useful official references

- Figma's Claude Code plugin setup:
  <https://help.figma.com/hc/en-us/articles/39888612464151-Claude-Code-and-Figma-Set-up-the-MCP-server>
- MCP server development:
  <https://modelcontextprotocol.io/docs/2026-07-28/develop/build-server>
- Claude Code MCP configuration:
  <https://docs.anthropic.com/en/docs/claude-code/mcp>

