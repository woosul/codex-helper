---
title: P2 numeric-net compatibility copy
description: Isolated KiCad 10 named-net conversion and static preservation evidence for EasyEDA import testing.
date: 2026-10-04
tags: [easyeda, kicad, compatibility, verification]
---

# P2 호환 변환사본

검증 시각: 2026-10-04 17:29:44 UTC.

원본: `/Users/denny/Project/kicad/kicad-integration-test/`의 PCB/SCH/PRO 3파일. 원본은 읽기 전용으로 취급했다. 시작/종료 SHA-256은 모두 동일하다. 세부 해시는 `verification.json`에 기록했다.

## 변환 범위

`convert.py`는 외부 패키지 없이 재귀 S-expression 파서로 전체 PCB를 읽는다. 파싱한 노드 위치에만 수정을 적용한다. 넷 이름의 사전순으로 ID를 결정한다: `/GND=1`, `/LED_A=2`, `/SW_VBAT=3`, `/VBAT=4`; 0은 빈 넷이다.

- 최상위 `(net ID "name")` 테이블 5행을 추가했다.
- 패드 10개는 `(net ID "name")`로 변환했다.
- 트랙 8개는 `(net ID)`로 변환했다.
- PCB 버전 `20260206`, generator version `10.0`, 두께 `1.6`, stackup 부재를 유지했다.
- SCH와 PRO는 원본 바이트를 그대로 복사했다.

## 검증

넷을 원래 이름으로 정규화하면 원본과 전체 AST가 동일하다. 넷 변경만 역적용하면 원본 PCB의 바이트가 완전히 복원된다. 따라서 좌표, 폭, 레이어, 풋프린트, 패드 형상 및 기타 비넷 내용이 유지된다. 18개 숫자 참조는 모두 원래 넷 이름으로 해석된다. 4개 풋프린트, 10개 패드, 8개 트랙을 유지한다. 패드별/트랙별 대조 자료는 `verification.json`에 있다.

설치된 공식 KiCad CLI 10.0.6의 `pcb export stats --format json`을 변환사본에 1회 실행했다. 종료 코드 0, stderr 없음. 부품 4개, 패드 10개, 최소 트랙 폭 0.35 mm, 두께 1.6 mm를 확인했다. 결과는 `kicad-stats.json`이다. CLI는 격리 폴더 안에 `.kicad_prl`을 생성했다. ZIP에는 포함하지 않았다. DRC 및 공식 포맷 재저장/정규화 검증은 실행하지 않았다.

## 인계 파일

- `import-source/`: 호환 PCB + 원본과 동일한 SCH/PRO.
- `Project2-Net-Compatibility.zip`: 위 3파일만 루트에 수록. 압축 해제 바이트 일치 확인.
- `verification.json`: 구조 대조, 넷 매핑, 패드/트랙 목록, 해시, CLI 결과.
- `kicad-stats.json`: 공식 CLI 통계.
- `convert.py`: 실제 실행한 변환 스크립트. 새 출력 디렉터리만 허용한다.

EasyEDA UI, MCP 서버, 앱 설정은 조작하지 않았다. 실제 가져오기 후 부품 4 / 패드 넷 10 / 트랙 8 및 각 넷·좌표를 대조하는 단계가 남아 있다.

**트레이드오프:** 넷 형식만 바꾸어 원인을 분리했고 원본 내용 보존을 검증했다. 전체 구버전 변환은 아니며 EasyEDA 실제 가져오기 성공, 두께 및 3D 보존은 보장하지 않는다.
