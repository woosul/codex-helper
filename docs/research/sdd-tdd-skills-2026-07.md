# SDD/TDD 스킬 조사와 추천

조사일: 2026-07-19

## 요약 추천

- TDD: 이미 설치된 [`obra/superpowers`](https://github.com/obra/superpowers)의 `test-driven-development`를 유지한다. 같은 역할의 중복 스킬은 설치하지 않는다.
- 가벼운 SDD: 현재 설치된 `brainstorming → writing-plans → subagent-driven-development/executing-plans → test-driven-development → verification-before-completion` 흐름을 기본으로 사용한다.
- 명시적인 PRD 스킬이 필요하면 [`addyosmani/agent-skills@spec-driven-development`](https://skills.sh/addyosmani/agent-skills/spec-driven-development)를 선택적으로 추가한다.
- 명세를 장기 원본으로 삼고 constitution/spec/plan/tasks/analyze/converge까지 프로젝트 표준화하려면 [GitHub Spec Kit](https://github.com/github/spec-kit)를 프로젝트 단위로 평가한다. 전역 기본값으로 자동 설치하지 않는다.

## 조사 방법

2026-07-19에 `skills.sh`와 `npx skills find`로 실제 카탈로그를 조회하고 원본 저장소, 라이선스, Codex 통합, 트리거 범위, 현재 하네스와의 중복을 비교했다.

- `spec driven development`: Addy Osmani 스킬 14.5K installs로 최상위.
- `test driven development`: Superpowers TDD 170.7K installs, Addy Osmani TDD 12.9K installs.
- `writing plans`: Superpowers writing-plans 189.9K installs.

설치 수는 시점 스냅샷이며 품질 보증이 아니다. 최종 선택은 원본 내용과 운용 적합성을 기준으로 했다.

## 후보 비교

| 후보 | 트리거와 산출물 | 유지보수·라이선스·Codex | 중복/비용 | 권장 |
|---|---|---|---|---|
| [Superpowers](https://github.com/obra/superpowers) TDD + planning stack | 기능/버그 구현 전에 RED-GREEN-REFACTOR, 승인된 설계를 세부 계획과 검증 단계로 변환 | 활발한 release, Codex 서브에이전트 지원, MIT | 현재 설치됨. 별도 명시적 SDD 이름은 없지만 이 저장소가 실제로 사용한 spec→plan→TDD 흐름과 일치 | **기본 유지** |
| [Addy Osmani spec-driven-development](https://github.com/addyosmani/agent-skills/tree/main/skills/spec-driven-development) | 새 프로젝트·기능·중요 변경에서 목표, 명령, 구조, 스타일, 테스트, 경계를 포함한 PRD 작성 | 저장소가 Codex native plugin과 skills CLI를 지원, MIT, 카탈로그 14.5K installs | Superpowers brainstorming/writing-plans와 일부 겹친다. PRD 템플릿을 명시적으로 원할 때 가치가 있다. | **선택 설치** |
| [GitHub Spec Kit](https://github.com/github/spec-kit) | constitution → specify → plan → tasks → analyze → implement → converge의 지속 산출물 그래프 | GitHub 관리, MIT, 2026-07-17 v0.13.0, Codex는 `.agents/skills` 통합 지원 | 강력하지만 프로젝트 구조와 명령이 늘고 기존 Superpowers와 상당히 겹친다. 단순 변경에는 과하다. | **대형/장기 프로젝트 파일럿** |
| Addy Osmani TDD | RED-GREEN-REFACTOR와 폭넓은 테스트 전략 | Codex plugin 지원, MIT, 12.9K installs | 이미 설치된 Superpowers TDD와 역할 충돌 가능 | 설치하지 않음 |

## 추천 운용안

### 기본: 현재 설치 스택

```text
요구 탐색 → 설계 명세 → 구현 계획 → failing test → 최소 구현 → fresh verification → review
brainstorming  writing-plans  test-driven-development  verification-before-completion
```

이 흐름은 Karpathy 4원칙과도 직접 맞물린다. 구현 전 가정과 트레이드오프를 드러내고, 최소 구현을 테스트로 고정하며, 변경 범위를 계획 항목에 추적하고, 완료 주장을 새 증거로 검증한다.

### 선택 1: PRD 작성을 더 엄격하게

Addy Osmani의 SDD 스킬 하나만 선택 설치한다. 먼저 임시 디렉터리에서 `SKILL.md`와 참조 파일, 라이선스를 검토한 뒤 이 저장소의 `sources/skills/`와 manifest로 편입한다.

```bash
npx skills add addyosmani/agent-skills --skill spec-driven-development
```

직접 설치 명령은 탐색용이다. 이 하네스에 영구 채택할 때는 사용자 가이드의 “스킬 추가” 절차를 따라 원본과 버전을 Git으로 관리한다. Superpowers `brainstorming`과 자동 트리거가 겹치지 않도록 description을 “명시적으로 PRD를 요청하거나 중요 변경일 때”로 좁히는 것이 좋다.

### 선택 2: 명세가 장기 시스템 원본인 프로젝트

Spec Kit은 단일 스킬보다 프로젝트 도구에 가깝다. Codex 통합은 `.agents/skills`에 `$speckit-*` 명령을 설치하며, spec/plan/tasks 간 일관성 분석과 수렴 루프를 제공한다. 새 핵심 제품이나 규제·감사 추적성이 필요한 저장소 한 곳에서 먼저 파일럿하고, 기존 프로젝트 전체에 전역 적용하지 않는다.

## 설치하지 않은 이유

TDD 스킬을 두 개 활성화하면 예외 규칙, 테스트 범위, refactor 시점이 서로 달라 에이전트가 어느 계약을 따라야 하는지 모호해질 수 있다. 현재 Superpowers TDD는 실제 이 저장소 구현에서 실패 테스트 확인과 최소 구현 루프를 수행했으므로 검증된 기본값이다. SDD도 동일하게, 현재 planning stack이 부족하다는 구체적 증거가 생기기 전에는 추가 도구를 최소화한다.
