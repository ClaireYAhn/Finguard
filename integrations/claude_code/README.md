# Claude Code hooks

Copy `settings.example.json` into `.claude/settings.json` (project) or `~/.claude/settings.json`, adjust the path, and set
`FINGUARD_URL`, `FINGUARD_APP_KEY` (the Coding Assistant app key) and optionally `FINGUARD_ROLE` (default `developer`) and `FINGUARD_FAIL_MODE=open|closed` (default closed).

Format notes (from the Claude Code hooks docs, https://code.claude.com/docs/en/hooks, read through a documentation fetch):
- stdin JSON: `prompt` for UserPromptSubmit; `tool_name`, `tool_input`, `tool_use_id` for PreToolUse.
- UserPromptSubmit blocks with stdout `{"decision":"block","reason":"..."}` (exit 0). The hook cannot rewrite the prompt, so FinGuard `modify` results are also blocked with a "remove the sensitive data" reason.
- PreToolUse uses `hookSpecificOutput.permissionDecision` (`deny`, `ask`) with `permissionDecisionReason`. FinGuard `escalate` maps to `ask`; `block`/`modify` map to `deny`. `updatedInput` is deliberately not used.

**VERIFY AGAINST CLAUDE CODE DOCS**: these scripts were not exercised inside a live Claude Code session in this build; only the hook logic was tested (tests/test_integrations.py) and against the running guard API.
