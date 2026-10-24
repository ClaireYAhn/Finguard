import type { App } from '../types'

export const KEY_PLACEHOLDER = 'YOUR_FINGUARD_APP_KEY'

export function buildSnippets(app: App, publicUrl: string, key?: string | null): { id: string; label: string; items: { title: string; code: string }[] }[] {
  const url = (publicUrl || window.location.origin).replace(/\/+$/, '')
  const k = key || KEY_PLACEHOLDER
  const model = app.model || 'MODEL_NAME'
  const role = app.default_role || 'user'
  const hooks = JSON.stringify(
    {
      hooks: {
        UserPromptSubmit: [{ hooks: [{ type: 'command', command: 'python3 /path/to/finguard/integrations/claude_code/finguard_user_prompt_hook.py' }] }],
        PreToolUse: [{ matcher: '*', hooks: [{ type: 'command', command: 'python3 /path/to/finguard/integrations/claude_code/finguard_pretooluse_hook.py' }] }],
      },
    },
    null,
    2,
  )
  return [
    {
      id: 'anthropic', label: 'Anthropic Python SDK',
      items: [{ title: 'Python', code: `import anthropic\n\nclient = anthropic.Anthropic(\n    base_url="${url}",\n    api_key="${k}",\n)\n\nmessage = client.messages.create(\n    model="${model}",\n    max_tokens=512,\n    messages=[{"role": "user", "content": "Hello"}],\n)\nprint(message.content[0].text)` }],
    },
    {
      id: 'openai', label: 'OpenAI Python SDK',
      items: [{ title: 'Python', code: `from openai import OpenAI\n\nclient = OpenAI(\n    base_url="${url}/v1",\n    api_key="${k}",\n)\n\nresp = client.chat.completions.create(\n    model="${model}",\n    messages=[{"role": "user", "content": "Hello"}],\n)\nprint(resp.choices[0].message.content)` }],
    },
    {
      id: 'curl-messages', label: 'curl /v1/messages',
      items: [{ title: 'curl', code: `curl ${url}/v1/messages \\\n  -H "x-api-key: ${k}" \\\n  -H "content-type: application/json" \\\n  -H "anthropic-version: 2023-06-01" \\\n  -d '{"model": "${model}", "max_tokens": 512, "messages": [{"role": "user", "content": "Hello"}]}'` }],
    },
    {
      id: 'curl-chat', label: 'curl /v1/chat/completions',
      items: [{ title: 'curl', code: `curl ${url}/v1/chat/completions \\\n  -H "Authorization: Bearer ${k}" \\\n  -H "content-type: application/json" \\\n  -d '{"model": "${model}", "messages": [{"role": "user", "content": "Hello"}]}'` }],
    },
    {
      id: 'claude-code', label: 'Claude Code hooks',
      items: [
        { title: '.claude/settings.json', code: hooks },
        { title: 'Environment variables', code: `export FINGUARD_URL="${url}"\nexport FINGUARD_APP_KEY="${k}"` },
      ],
    },
    {
      id: 'agent', label: 'Agent guard',
      items: [{ title: 'curl', code: `curl -X POST ${url}/v1/guard/tool-call \\\n  -H "x-api-key: ${k}" \\\n  -H "content-type: application/json" \\\n  -d '{"agent_id": "my-agent", "tool": "send_email", "arguments": {"to": "someone@example.com"}, "role": "${role}"}'` }],
    },
  ]
}
