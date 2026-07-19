# Sources and adaptation notes

The harness design follows current Codex documentation:

- OpenAI, [Subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents)
- OpenAI, [Build skills](https://learn.chatgpt.com/docs/build-skills)
- OpenAI, [Advanced configuration](https://learn.chatgpt.com/docs/config-file/config-advanced)
- OpenAI, [Rules](https://learn.chatgpt.com/docs/agent-configuration/rules)

The internal/external loop distinction is adapted from Phil Schmid's [Agents: Inner Loop vs Outer Loop](https://www.philschmid.de/inner-loop-vs-outer-loop). The fresh-context, file/Git-memory idea is informed by snarktank's [Ralph](https://github.com/snarktank/ralph), while deliberately omitting an unbounded autonomous runner.

`parallel-review` and `dual-loop-review` are local adaptations designed for Codex's native agent, profile, sandbox, and skill surfaces. No third-party source code is vendored. The manifest records upstream references, `local-adaptation` license status, and the last review date so later maintenance can identify provenance and staleness.
