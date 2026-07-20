# 사용자 가이드

이 저장소는 Codex 전역 지침, 호스트별 설정, read-only 에이전트, 스킬, 유틸리티의 원본을 Git으로 관리하고 각 런타임 위치에는 개별 심볼릭 링크만 배선한다. `~/.codex/config.toml`도 선택된 `sources/config/config-<host>.toml`을 가리키는 `global-config` 링크다.

## 처음 설치와 다른 머신 연결

```bash
git clone <your-repository-url> codex-helper
cd codex-helper
./install.sh --host <machine-name>
```

새 머신 이름이 필요하면 먼저 `./bin/codex-harness host init <machine-name>`으로 safe default를 복사한 `sources/config/config-<machine-name>.toml`을 만들고 검토·커밋한다. 설치 계획을 확인한 다음 적용하고, `$HOME/.local/bin`을 `PATH`에 넣은 뒤 Codex를 다시 시작한다. 자세한 절차는 `docs/cross-machine-bootstrap.md`에 있다.

## 일상 운용

변경 전후에 아래 순서로 상태를 확인한다.

```bash
codex-harness plan
codex-harness status --json
codex-harness inventory --json
codex-harness doctor --json
```

- `plan`: 쓰기 없이 예상 변경을 보여준다.
- `status`: 링크와 설정 드리프트를 찾는다.
- `inventory`: 자산 ID, 종류, 버전, 원본, 대상, 현재 상태를 한 번에 본다.
- `list --kind skills`: 스킬만 필터링한다. `agents`, `profiles`, `rules`, `utilities`도 가능하다.
- `version [ASSET]`: 하네스 또는 특정 자산 버전을 확인한다.
- `snapshot --json`: 수동 유지보수 전 복구 지점을 만든다.
- `apply --yes`: 검토한 계획을 트랜잭션으로 적용한다. 실패하면 직전 스냅샷으로 자동 복구한다.
- `restore ID --yes`: 선택한 스냅샷으로 되돌린다.
- `unlink --yes`: 이 하네스가 소유한 링크를 해제하고 기록된 config 원본을 권한 `0600`의 실제 파일로 만든다.

정상 업데이트는 다음 네 명령으로 충분하다.

```bash
git pull --ff-only
codex-harness plan
codex-harness apply --yes
codex-harness doctor
```

## 제공 워크플로

### 기능 전달 워크플로

`$feature-delivery`는 사용자가 명시적으로 요청할 때만 실행한다. 작업 크기, 파일 수, 모호성 또는 구현 복잡성만으로 자동 활성화하지 않는다.

`feature-delivery`가 없거나 머신 로컬에서 비활성화되어 있으면 전역 지침은 사용할 수 없는 스킬을 요구하지 않는다. 루트는 누락된 스킬을 호출하지 않고 인라인 또는 루트가 선택한 다른 워크플로로 계속할 수 있다.

실행 전략은 **기본 Root-Inline**이다. 마스터가 직접 계획, 구현, 리뷰, 검증할 수 있다. 다만 `$feature-delivery` 명시 호출은 서브에이전트 사용을 허가하며 별도 서브에이전트 요청은 필요하지 않다. 스킬 이름을 단순 지칭하거나 계약을 수정하는 것은 호출이 아니다.

마스터가 planner/scanner/developer/reviewer/verifier에 작업을 위임하면 해당 범위는 서브에이전트가 수행하고, 마스터는 같은 작업을 중복 수행하지 않는다. 마스터는 조정, 통합 또는 명확히 겹치지 않는 작업만 계속한다. 단일 developer에게 별도 worktree를 강제하지 않는다. 순차 위임도 active checkout을 사용할 수 있다. 다만 두 번째 동시 developer를 시작할 때는 worktree 존재를 확인하고, 없으면 생성한 뒤 작업을 시작한다. 동시에 실행되는 writable developer는 같은 checkout을 공유하지 않는다. developer 프로필의 기본값은 `workspace-write`이고 실제 편집은 **사용자/시스템 권한 경계** 안에서만 가능하다. 수정 루프는 **기본 세 번**이고 최종 통합과 **커밋과 푸시**는 루트 책임이다.

활동 표시는 루트가 `role instance - task name` 형식으로 부여한다. 예: `developer 1 - implement role badges`, `reviewer 2 - review role quality`. 반복 역할 번호는 새 스레드마다 단조 증가하며, 동일 스레드에 follow-up을 보낼 때만 기존 번호를 재사용한다. native badge의 폭과 **말줄임**은 **client-owned**이므로 하네스가 설정할 수 없으며, 루트는 전체 **본문 label**을 dispatch·progress·completion 본문에 유지한다.

### 네이티브 병렬 리뷰

Codex 앱 또는 대화형 CLI 작업에서 `$parallel-review`를 명시적으로 호출한다. scanner, reviewer, verifier가 독립적인 read-only 관점을 반환하고 루트 에이전트가 증거를 재확인해 통합한다.

부모 작업이 서브에이전트 종료까지 유지되어야 하므로 `codex exec --ephemeral`과 함께 사용하지 않는다. 자동화에서 쓸 때는 persistent `codex exec`를 사용한다.

### 내부/외부 이중 리뷰 루프

로컬 테스트 증거를 만든 후 별도 read-only Codex 프로세스로 한 번 더 검토한다.

```bash
codex-external-review --repo "$PWD" --cycle 1 --evidence .codex-loop/evidence.md
```

외부 프로세스는 ephemeral이며 JSON 스키마에 맞는 `pass`, `changes_requested`, `blocked` 판정만 반환한다. 수정 루프는 최대 세 번이고, 모든 지적은 현재 작업에서 다시 검증한다.

## 스킬 추가

외부 스킬을 바로 전역 디렉터리에 복사하지 말고 먼저 원본과 라이선스를 검토한다. 채택할 때는 다음 순서를 사용한다.

1. `sources/skills/<name>/`에 `SKILL.md`와 필요한 `references/`, `schemas/`, `agents/`를 둔다.
2. `manifest.toml`에 고유한 자산 ID, `category = "skills"`, 원본, 대상, 버전, upstream, license, `last_reviewed`를 기록한다.
3. 계약 테스트를 추가하고 `./tools/run-tests`를 실행한다.
4. `codex-harness plan`으로 대상이 `$HOME/.agents/skills/<name>`인지 확인한다.
5. `codex-harness apply --yes`와 `codex-harness doctor`를 실행한 뒤 Git에 커밋한다.

새 버전은 먼저 `sources/`를 갱신하고 manifest의 자산 버전과 `last_reviewed`를 올린다. `inventory`의 source/target/version을 검토한 뒤 적용한다. 설치 편의보다 재현 가능한 원본과 명시적인 출처가 우선이다.

## 스킬 ON/OFF

두 방법을 목적에 따라 선택한다. Git으로 공유할 기본값은 `manifest.toml`, 이 머신에서만 적용할 local override는 `~/.codex/.codex-helper/preferences.toml`이 원본이다. 로컬 선택이 manifest 기본값보다 우선한다.

현재 상태는 다음 명령으로 확인한다.

```bash
codex-harness skill list --json
codex-harness skill status parallel-review --json
```

### 방법 1: 모든 머신에 공유하는 기본값

해당 skill 자산 stanza의 `enabled`만 바꾼다. 생략하면 `true`다.

```toml
[[assets]]
id = "skill-parallel-review"
category = "skills"
enabled = false
```

그 다음 `codex-harness plan`, `codex-harness apply --yes`, `codex-harness doctor`로 검증하고 manifest 변경을 커밋한다. 효과적으로 OFF인 스킬의 원본은 그대로 남고, 하네스가 소유한 일치 링크만 제거된다.

### 방법 2: 현재 머신에서만 선택

```bash
codex-harness skill disable parallel-review
codex-harness skill enable parallel-review
codex-harness skill reset parallel-review
```

- `disable`: 로컬 OFF를 기록하고 일치하는 링크를 즉시 제거한다.
- `enable`: 로컬 ON을 기록하고 링크를 즉시 만든다. manifest 기본값이 OFF여도 이 머신에서는 ON이다.
- `reset`: 로컬 선택을 지우고 manifest 기본값으로 돌아간다.

두 목록에 같은 스킬이 들어가거나 알 수 없는 asset ID가 있으면 하네스가 fail-closed한다. 일반 파일, 디렉터리, 외부 링크가 대상 위치를 차지하면 toggle은 preference와 대상을 모두 변경하지 않고 conflict를 반환한다.

링크를 손으로 지우면 local override가 없으므로 `status`가 드리프트로 보고하고 다음 `apply`가 기본값에 맞춰 복구한다. 새 상태는 새 Codex 작업부터 확실히 적용된다. 이미 열린 작업은 로드된 스킬 지침을 문맥에 보유할 수 있다.

## 설정과 호스트 선택

- 안전한 미등록 머신 기본값: `sources/config/config-default.toml`
- 머신별 Git 추적 설정: `sources/config/config-<name>.toml`
- 선택 순서: `--host` > `CODEX_HELPER_HOST` > 소문자 short hostname
- 인증 정보와 토큰: 프로젝트 루트의 Git 제외 파일 `.env-<name>`

`GEMS.local`은 `gems`로 정규화된다. 명시 옵션이나 환경 변수가 가리키는 파일이 없으면 오타로 보고 fail-closed하고, 자동 감지한 hostname만 미등록이면 plan에 fallback을 표시하며 default를 선택한다.

전역 설정 대상은 런타임 `CODEX_HOME` 값과 무관하게 항상 `$HOME/.codex/config.toml`이다. 선택된 Git 원본으로 심볼릭 링크하며, 두 번째 적용은 no-op이다. 호스트 변경은 plan/status에서 drift로 나타난다.

호스트별 config에는 머신 경로, MCP 정의, 플러그인 선택, 프로젝트 신뢰 설정과 UI 설정을 포함할 수 있다. 모든 v0.4.1 config에는 `features.multi_agent = true`, `agents.max_threads = 4`, `agents.max_depth = 1`이 필요하다.

Git config에는 비밀값만 제외한 해당 머신의 실제 설정을 둔다. n8n 인증 헤더처럼 민감한 값은 `.env-gems` 또는 `.env-rock`에 두고, Git에는 대응하는 `.example`만 남긴다. `bin/codex-mcp-env`가 호스트 파일을 읽어 MCP 프로세스에 값을 전달하며, `doctor`는 추적 TOML의 literal bearer 값을 검사한다.

## 장애 대응

`status`가 drift를 보고하면 먼저 `plan`을 읽는다. 예상하지 못한 실제 파일이나 다른 링크가 대상에 있으면 덮어쓰기 전에 소유자를 확인한다. 최근 적용이 문제라면 적용 결과에 표시된 snapshot ID로 복구한다.

```bash
codex-harness restore SNAPSHOT_ID --yes
codex-harness doctor --json
```

하네스 제거 전에는 저장소 폴더부터 지우지 말고 `codex-harness unlink --yes`를 먼저 실행한다.
