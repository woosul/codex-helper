# 사용자 가이드

이 저장소는 Codex 전역 지침, 설정 조각, read-only 에이전트, 스킬, 유틸리티의 원본을 Git으로 관리하고 각 런타임 위치에는 개별 심볼릭 링크만 배선한다. `~/.codex/config.toml`만 예외로, 사용자 설정을 보존하면서 manifest 소유 키만 병합하는 실제 파일이다.

## 처음 설치와 다른 머신 연결

```bash
git clone <your-repository-url> codex-helper
cd codex-helper
./install.sh --host <machine-name>
```

새 머신 이름이 필요하면 먼저 `./bin/codex-harness host init <machine-name>`으로 `sources/config/hosts/<machine-name>.toml`을 만들고 커밋한다. 설치 계획을 확인한 다음 적용하고, `$HOME/.local/bin`을 `PATH`에 넣은 뒤 Codex를 다시 시작한다. 자세한 절차는 `docs/cross-machine-bootstrap.md`에 있다.

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
- `unlink --yes`: 이 하네스가 소유한 배선과 설정 키만 해제한다.

정상 업데이트는 다음 네 명령으로 충분하다.

```bash
git pull --ff-only
codex-harness plan
codex-harness apply --yes
codex-harness doctor
```

## 제공 워크플로

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

스킬 상태의 원본은 `manifest.toml`이다. 별도 숨은 토글 파일을 두지 않는다.

- ON: 해당 스킬 자산 stanza를 manifest에 유지하고 `codex-harness apply --yes`를 실행한다.
- OFF: 해당 stanza만 manifest에서 제거하고 `codex-harness plan`을 검토한 뒤 적용한다. 기존 대상이 여전히 하네스 원본을 가리킬 때만 안전하게 링크를 제거한다. `sources/skills/<name>`은 남겨 두면 언제든 stanza를 복구할 수 있다.
- 머신별로만 잠시 끄고 싶다면 전역 manifest를 바꾸기보다 해당 머신에서 작업 범위와 호출 조건을 제한한다. 링크를 손으로 지우면 `status`가 드리프트로 보고하므로 상시 운용 방식으로 사용하지 않는다.

변경은 하나의 커밋으로 남겨 다른 머신에서도 같은 ON/OFF 상태를 재현한다. 스킬의 자동 발동 범위는 `SKILL.md` frontmatter의 `description`으로 좁히고, 수동 호출 전용이면 설명에 “명시적으로 요청할 때”를 적는다.

## 설정과 호스트 오버레이

- 공통 비밀 없는 설정: `sources/config/base.toml`
- 머신별 추적 설정: `sources/config/hosts/<name>.toml`
- 머신별 비추적 설정: `sources/config/hosts/<name>.local.toml`
- 인증 정보와 토큰: 환경 변수 또는 Codex 자격 증명 저장소

라이브 `config.toml` 전체를 링크하거나 덮어쓰지 않는다. 하네스는 자신이 관리하는 TOML 경로만 상태 파일에 기록해 이후 업데이트와 unlink에서 사용자 소유 설정을 보존한다.

## 장애 대응

`status`가 drift를 보고하면 먼저 `plan`을 읽는다. 예상하지 못한 실제 파일이나 다른 링크가 대상에 있으면 덮어쓰기 전에 소유자를 확인한다. 최근 적용이 문제라면 적용 결과에 표시된 snapshot ID로 복구한다.

```bash
codex-harness restore SNAPSHOT_ID --yes
codex-harness doctor --json
```

하네스 제거 전에는 저장소 폴더부터 지우지 말고 `codex-harness unlink --yes`를 먼저 실행한다.
