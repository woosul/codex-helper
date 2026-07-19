# Codex 외부 리뷰 에이전트 조사

조사일: 2026-07-19

## 결론

Claude Code에서 Codex를 계획·코드 리뷰 전용 에이전트로 호출하는 기본 선택은 OpenAI 공식 [`codex-plugin-cc`](https://github.com/openai/codex-plugin-cc)다. 현재 작업 흐름을 가장 적게 바꾸면서 read-only 리뷰, 백그라운드 실행, 상태·결과 조회, 세션 인계를 제공하고 로컬 Codex 인증과 설정을 그대로 사용한다.

이 저장소의 권장 계층은 다음과 같다.

1. Claude Code → Codex 리뷰: 공식 `codex-plugin-cc`의 `/codex:review --background` 또는 설계 반론용 `/codex:adversarial-review`.
2. Codex 내부 독립 검토: `$parallel-review`와 `~/.codex/agents/*.toml` read-only 커스텀 에이전트.
3. 스크립트·CI·단일 외부 루프: `codex review` 또는 `codex exec --sandbox read-only`와 구조화 출력.
4. Claude/Codex/Gemini 등 실제 모델 공급자 다양성이 필요할 때만 MCO 같은 별도 오케스트레이터.

## 공식적으로 지원되는 형태

| 형태 | 적합한 용도 | 경계와 주의점 |
|---|---|---|
| Codex 커스텀 서브에이전트 | 한 Codex 작업 안에서 보안·정확성·테스트 관점을 병렬 분리 | [`Subagents`](https://learn.chatgpt.com/docs/agent-configuration/subagents.md)는 read-heavy 병렬 작업을 우선 권장한다. 자식은 부모 sandbox를 상속하므로 reviewer 파일도 `sandbox_mode = "read-only"`로 고정한다. |
| `codex review` | 미커밋 변경, base branch diff, 특정 commit의 표준 리뷰 | 공식 [`developer commands`](https://learn.chatgpt.com/docs/developer-commands?surface=cli#cli-codex-review)에 대상 선택이 내장되어 있다. 구현 에이전트와 프로세스를 분리하기 쉽다. |
| `codex exec` | CI, hook, 다른 에이전트가 호출하는 단발 작업 | [`Non-interactive mode`](https://learn.chatgpt.com/docs/non-interactive-mode.md)의 read-only sandbox, JSONL, output schema/last-message를 사용하면 계약화하기 쉽다. 네이티브 서브에이전트를 쓸 때는 부모 thread가 필요하므로 `--ephemeral`을 빼야 한다. |
| `codex mcp-server` | 다른 에이전트가 Codex 자체를 MCP 도구로 소비 | 공식 CLI의 stable 명령이지만 Claude Code에는 공식 플러그인이 더 직접적이다. 과거 Codex 0.58 환경에서 self-MCP handshake가 멈춘 [공개 이슈](https://github.com/openai/codex/issues/6664)도 있어 도입 전 현재 버전에서 별도 검증한다. |
| 자동 승인 reviewer | sandbox 밖 명령 승인을 별도 분류기로 판단 | 코드 품질 리뷰가 아니라 승인 경계다. sandbox 권한을 확장하지 않으며 보안 보증으로 간주하지 않는다. |

## Claude Code에서의 권장 구성

공식 플러그인은 2026-07-08 기준 v1.0.6을 공개했고 Apache-2.0 라이선스다. 설치는 Claude Code 안에서 다음 순서다.

```text
/plugin marketplace add openai/codex-plugin-cc
/plugin install codex@openai-codex
/reload-plugins
/codex:setup
```

일상 리뷰는 다음 정도로 충분하다.

```text
/codex:review --base main --background
/codex:status
/codex:result
```

구현 방향 자체를 압박하려면 `/codex:adversarial-review --background <focus>`를 사용한다. 리뷰 gate는 Claude의 Stop hook에서 Codex 리뷰를 반복할 수 있지만 공식 문서도 장시간 루프와 사용량 소진을 경고하므로 기본 활성화하지 않는다. 현재 사용 중인 커스텀 Claude 리뷰 연결이 안정적이라면 즉시 교체할 필요는 없고, 공식 플러그인을 기준선으로 기능과 장애 처리를 비교하면 된다.

## 커뮤니티 사례 비교

| 도구 | 장점 | 이 하네스에서의 판단 |
|---|---|---|
| [AWS Labs CLI Agent Orchestrator](https://github.com/awslabs/cli-agent-orchestrator/blob/main/docs/codex-cli.md) | provider별 역할, MCP handoff, session-scoped Codex 설정 주입. reviewer 예시는 `approval_policy = "never"`와 read-only sandbox를 사용한다. | 복잡한 supervisor/developer/reviewer 조직이 필요할 때 참고. 단순 Claude→Codex 리뷰에는 무겁다. |
| [MCO](https://github.com/mco-org/mco) | Claude, Codex, Gemini 등 여러 CLI를 병렬 비교하고 raw 답변, JSONL, debate/synthesis를 보존한다. 기본 review mode는 read-only다. | 진짜 외부 모델 다양성이 필요한 3차 검증에 적합. worktree는 직접 관리하지 않으므로 병렬 쓰기에는 별도 격리가 필요하다. |
| [Orca](https://github.com/stablyai/orca) | 각 에이전트를 별도 Git worktree에 배치하고 여러 결과를 비교·병합한다. | 다수의 구현 에이전트를 동시에 운용할 때 적합. 리뷰 전용 하네스의 필수 의존성으로 넣지 않는다. |
| [codex-orchestrator](https://github.com/kingbootoshi/codex-orchestrator) | Claude Code가 tmux의 Codex job을 시작·조회·재지시하고 read-only sandbox를 선택할 수 있다. | 가벼운 백그라운드 CLI 사례로 유용하지만 공식 플러그인보다 우선하지 않는다. 공개 release가 없는 점도 고려한다. |

## 이 저장소에 적용한 선택

- `parallel-review`: persistent 부모 task 아래 scanner/reviewer/verifier를 bounded read-only로 실행한다.
- `dual-loop-review`: 신선한 로컬 검증 증거 뒤 별도 `codex exec --ephemeral --sandbox read-only` 프로세스를 최대 세 번 호출하고 JSON schema verdict를 강제한다.
- 쓰기 권한과 최종 판정은 루트 에이전트에만 둔다.
- 외부 오케스트레이터나 Claude 플러그인은 사용자 런타임 소유이므로 이 저장소가 자동 설치하거나 설정을 덮어쓰지 않는다.

실제 스모크에서는 dual-loop 단일 외부 리뷰가 `pass`를 반환했고 checkout hash가 유지되었다. parallel-review는 ephemeral 부모에서 thread 저장 문제가 발생했지만 persistent 부모에서는 세 역할과 루트 통합이 완료되었고 diff hash가 유지되었다. 이 차이를 스킬과 운영 문서의 명시적 계약으로 반영했다.
