#!/usr/bin/env python3
"""Claude Code UserPromptSubmit hook: sends the prompt to FinGuard input rails; blocks when FinGuard says so."""
import json
import sys

from _common import emit, error_output, post, prompt_output

if __name__ == "__main__":
    data = json.load(sys.stdin)  # fields per Claude Code docs: session_id, transcript_path, cwd, hook_event_name, prompt, ...
    try:
        emit(prompt_output(post("/v1/guard/prompt", {"text": data.get("prompt", "")})))
    except Exception as exc:  # noqa: BLE001
        emit(error_output("UserPromptSubmit", exc))
