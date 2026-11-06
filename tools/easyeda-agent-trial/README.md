---
title: EasyEDA Agent v0.21.7 isolated trial
description: Verified release files and MCP catalog, awaiting authorization for the distinct extension permission and local connection.
date: 2026-10-04
tags: [easyeda, mcp, trial]
---

## 다른 머신에서 복원

다음 명령은 이 디렉터리에서 실행한다. CLI와 확장은 릴리스 메타데이터의 SHA-256을 검증한 뒤 설치한다. 기존 파일이 고정 버전과 다르면 덮어쓰지 않는다.

```sh
python3 install-runtime.py
npm ci --ignore-scripts --prefix mcp
./bin/easyeda version
EASYEDA_BIN="$PWD/bin/easyeda" npm test --prefix mcp
```

`skills/`, MCP 원본, 패키지 잠금 파일, NOTICE와 릴리스 메타데이터는 Git으로 배포한다. 다운로드한 실행 파일·확장, `node_modules/`, `.runtime/` 및 반복 실행 로그는 제외한다. 설치 스크립트는 데몬·자동 실행·MCP 등록·확장 권한을 변경하지 않는다. 해당 머신의 EasyEDA 설치와 권한은 별도로 확인한다.

아래 상태와 검증 결과는 **2026-10-04의 기록**이다. 다른 머신의 현재 상태를 의미하지 않는다.

# 현재 상태

- 공식 릴리스 v0.21.7 ARM64 CLI/확장/스킬 SHA256 일치. `bin/easyeda version` → v0.21.7.
- annotated tag `148c409780ad212a5a9096f27a3f6bdbf52777f0` → commit `7dfa5f7ce8f6bd6c56f6ab493056fd49a663efcc`. 태그 API 증거는 artifacts 폴더.
- 확장 manifest 0.21.7 / EDA ~3.2.0 / UUID `4dae27407c1d43be98e8e210d45fe587`. 아직 EasyEDA에 import하지 않았다.
- 태그 NOTICE 및 manifest Apache-2.0 명시. 태그 루트 LICENSE 파일 없음. 현재 main의 라이선스나 최신버전과 혼합하지 않았다.
- 스킬은 release `skills.tar.gz`에서 그대로 설치. `~/.codex/skills/easyeda-agent` 링크 → 이 폴더 skills/easyeda-agent.
- `~/.easyeda-agent` 링크 → 이 폴더 .runtime(0700). 기존경로없음 확인후 생성했다.
- 태그내 MCP package/server metadata 0.18.3; 같은태그 소스이며 npm ci --ignore-scripts 실행(93deps).
- 실제 SDK stdio initialize/listTools 성공: 11개 도구. artifacts/tool-catalog.json.
- 실제 health 호출은 not_found: daemon을 아직 기동하지 않았음. 연결검증 통과로 간주하지 않는다.
- 시험용 MCP 클라이언트 프로세스는 종료했다. 자동 daemon/LaunchAgent는 만들지 않았다.

# 재개 조건 및 절차

새 확장의 External Interactions 권한, loopback127.0.0.1:60832, 자동연결/재연결에 대한 사용자 확인 대기. 승인 전 import/권한/daemon연결하지 않는다.

승인후 MCPPro/자체bridge가writer아님을확인하고,공식확장관리창에서 `easyeda-agent-connector-v0.21.7.eext`를import한다. 외부상호작용은공식메뉴에서허용하고자동업데이트는끄며,daemon은 `bin/easyeda daemon start --auto-update-skill=false --autosave-debounce 0 --host 127.0.0.1 --ports 60832-60832`로한개만시작한다. `EASYEDA_SKILLS_DIR`는이폴더skills,`EASYEDA_AUDIT_DIR`와`EASYEDA_WORKFLOW_DIR`는.runtime하위로지정한다. HOME은바꾸지않는다.

먼저health에서client/version/document를읽고,Project2는읽기비교만한다. 수정·삭제시험은Project1격리표식으로하고저장/문서닫기/재열기검증한다. typed도구우선,raw실행은기존사용자승인범위의검토된작은코드만허용된다. 실패를성공응답으로덮지않는다. P1/P2기존결과는 ../easyeda-mcp-pro-trial/VERIFICATION.md.

**트레이드오프:** 동일태그의CLI·확장·스킬과MCP카탈로그는검증됐지만,새확장권한승인전이므로EasyEDA실연결/설계CRUD는아직판정할수없다.
