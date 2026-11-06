---
title: EasyEDA Pro local integration verification
description: Verified MCPPro capability, preserved KiCad import baseline failures, and final P2 repaired DRC0/mm result.
date: 2026-10-04
tags: [easyeda, mcp, verification, pcb]
---

# 검증 상태 — 최종 repaired 갱신 2026-10-04 18:45 UTC

설치 앱: `/Applications/EasyEDA-Pro.app`, Pro **3.2.149.88089769 arm64**, global/Half Offline. 공개 확장 API **0.2.53**는 앱 안에서 실행되는 JavaScript/TypeScript API다. 외부 업체 REST API가 아니다. 중국 리전 전환이나 디버깅 포트 활성화는 하지 않았다.

## 현재 결론 — P2 repaired 완료

최종 편집 사본은 `/Users/denny/Project/easyeda/project2-net-compatibility/repaired/Project2-Repaired.eprj2`이다. 넷 이름 접두사 및 Channel ID·부품 메타데이터를 공식 Import Changes로 정합하고, PCB 표시 단위를 mm로 설정했다. 저장·실제 닫기·재열기 후 **DRC 오류 0·경고 0, mm 지속성, 4넷·10패드·1.6mm·4모델**을 확인했다. 구리 형상·외곽·부품 위치 및 보호 원본 7파일의 해시는 보존됐다.

공식 동기화가 VBAT 직선 하나를 중간 패드 위치에서 분할하여 트랙 객체는 **8→9개**이다. 분할 구간의 합집합이 원래 직선과 정확히 같음을 기계 검증했으며, 의미 보존 성공으로 수용됐다. 객체 수를 맞추기 위한 삭제·재배선은 하지 않았다. 로컬 STEP 4개는 다른 컴퓨터로 이동할 때 동반해야 한다. 외곽 stroke/aperture 차이는 남지만 확인된 Gerber 중심선·치수 변화는 없으며 실제 공장 CAM은 미검증이다.

- [최종 결과·P1/P2 운용 및 이동 제약](/Users/denny/Project/easyeda/project2-net-compatibility/repair-evidence/NETLIST-RECONCILE-RESULT.md)
- [최종 기계 검증·직선 합집합·보호 해시](/Users/denny/Project/easyeda/project2-net-compatibility/repair-evidence/netlist-reconcile-verification.json)

**아래 도구 시험과 Project2 원본 대조는 16:36 UTC의 역사적 baseline 기록이다.** 직접 가져오기의 넷/배선 손실과 DRC1은 해당 보존 baseline의 결과이며, 현재 repaired 사본의 상태가 아니다. baseline 실패 증거는 삭제하거나 성공으로 바꾸지 않았다.

## 도구별 결과

| 기능 | MCPPro 1.1.0 결과 | 검증/제약 |
|---|---|---|
| 설치/연결 | 통과 | npm integrity + 확장1.1.0;127.0.0.1:49620;공식External Interactions허용 |
| 자동 재연결 | 통과 | 서버 종료/재시작 후 UI 추가조작 없이 connected 및새조회 |
| 실제 MCP 호출 | 통과 | 공식 MCP SDK stdio client;118 tools. 현재 Codex nativecatalog 재발견은 별도미검증 |
| 회로 Text 생성 | 통과 | 저장/문서닫기/재열기 보존 |
| 회로 Text 수정/삭제 typed | 실패 | 성공응답이나 재열기 후원래텍스트복귀 |
| 회로 Text 공개API 우회 | 통과 | generic sch_PrimitiveObject.delete + 재생성;수정시ID변경 |
| 부품 생성/배치/회전 | 통과 | 실제4부품회로 및PCB 재열기지속 |
| 회로 wire/net/ERC | 통과 | P1 4nets,10pins,떠있는핀0,ERC0/0 |
| typed SCH→PCB sync | 실패 | 방향다른 SCH_Document.importChanges 호출;성공응답이실제변환아님 |
| 공개 PCB_Document.importChanges | 통과 | 회로UUID인수 +공식Apply ChangesUI후PCB4부품/패드넷 |
| PCB Arc.create | 실패 | 반환ID있으나저장/재열기후arcs0 |
| PCB Polygon/Polyline 외곽 | 통과 | 닫힌4직선+4arc 경로 재열기보존/3D둥근기판 |
| PCB 배선 | 통과 | 0.35mm Top선14 재열기보존,DRC0/0 |
| 3D 위치/회전 편집 | 통과 | UI모델수정+저장/닫기/재열기,공개API변환복구+다시재열기 |
| KiCad10 직접 가져오기 | 부분/실패 | P2부품/외곽보존,PCB넷/배선손실;아래비교 |

MCPPro 사용 조건은 PolyForm Noncommercial 1.0.0이며 사용자가 비상업적 시험이라고 확인했다. supplierId가 빈 generic header에 typed component modify를 쓰면 값이 잘못 채워지는 문제도 관찰했다. 공개 modify(null)로 P1 해당 필드를 정리하고 ERC0을 다시 확인했다.

## Project1 결과

설계: `/Users/denny/Project/easyeda/project1-liion-led/Project1-LiIon-LED.eprj2`

외부 보호형 1S Li-ion(3.7V/최대4.2V) → J1 → SW1 → R1 680Ω5%0.125W → D1 redLED → GND. J1은2.54mm2pin,SW1 TL3342F160QG,R1 0805W8J0681T5E,D1 **APT2012LSECK/J3-PRV**(P2의AP2012SURCK와다른의도적선정).

VBAT=J1.1+SW1.1/2;SW_VBAT=SW1.3/4+R1.1;LED_A=R1.2+D1.2(A);GND=D1.1(K)+J1.2. Board20×15mm,cornerR2mm,4parts/14tracks/0vias. ERC0errors0warnings,DRC0errors0warnings. 사용자mm요청에따라전역SCH/새PCB기본과현재표시mm설정;API좌표는기존mil단위를그대로사용. 설정창을다시열어SCHmm=1/새PCBmm=1/새Footprintmm=1이유지되는것까지확인했다.

제조사 Kingbright 데이터시트 APT2012LSECK-J3-PRV V8A2025-03-14: 광학/전기측정전류2mA,DC절대최대30mA(25°C). 라이브러리 `Test Current=30mA`는측정전류와최대전류를혼동하므로제조사값우선. 4.2V/Rmin646Ω에서Vf1.5V예시4.18mA/저항11.3mW,LED를0V로놓은보수적상한6.50mA/27.3mW. Vf1.5V를모든온도보장최소로가정하지않는다. 원본제조사자료:https://www.kingbrightusa.com/images/catalog/SPEC/APT2012LSECK-J3-PRV.pdf

3D실험: R1모델Z90°/X+1mm/Z+1mm로이동후재열기에서변환유지. 공개 `pcb_PrimitiveComponent.modify` otherProperty의3D Model Transform으로Z0°/offset0으로복구후재열기유지. 최종4모델실제렌더확인:[3D화면](artifacts/project1-final-3d.jpg). 문자열순서상rotationZ가4번째필드였으며표시mm와API39.37008mil환산을확인했다.

## Project2 원본 대조

원본은 `/Users/denny/Project/kicad/kicad-integration-test/`의최신3파일을사본으로만읽었다. 변환결과 `/Users/denny/Project/easyeda/project2-kicad-import/Project2-KiCad-Import.eprj2`. 파일3개SHA256은사본과동일하며작업후원본불변:[해시검증](artifacts/project2-original-integrity-final.json).

| 항목 | 원본 KiCad10 | P2 가져온 결과 | P1 신규작성 |
|---|---|---|---|
| 회로 부품 | 5(BT1외부배터리포함) | 5/부품Value원문보존 | 4(J1으로외부배터리표현) |
| 회로 연결 | 4nets | wire기반4nets/떠있는핀0;공식ERC풋프린트누락1 | 4nets/ERC0 |
| PCB 부품/패드 | 4/10 | 4/10,풋프린트명/XY보존 | 4/10 |
| PCB 패드네트 | 4net에10pad배정 | **10개모두빈값** | 4net정상 |
| 배선 | Top8개/폭0.35mm | **0개** | Top14개/폭0.35mm |
| 외곽 | 4line+4arc,22.177402×16.633048mm | 8Polyline,22.1774×16.6330mm | 닫힌Polyline1,20×15mm |
| 비아 | 0 | 0 | 0 |
| 기판 두께 | 1.6mm | **0.09mm/유전체층없음** | 1.6mm |
| 3D | KiCad10 STEP참조4 | 연결modelUUID0 | 모델4 |
| PCB DRC | 이번시험원본재실행안함 | Netlist mismatch1 | 0 |

가져오기는Import Document/원본스타일/자동footprint·3D치환OFF. ZIP은SCH/PCB/PRO만담았다(STEP미포함). 따라서3D없음은로컬KiCad환경변수참조및패키징/자동연결OFF가함께영향줄수있어,KiCad10변환결함이라고단정하지않는다. PCB넷과배선은원본파일에내장되어있지만재열기/공식원문/공식PCB넷리스트에서모두없어실제손실이다. [가져온PCB원문](artifacts/project2-imported-pcb-source.txt)에서LINE0,POLY8모두layer11,PAD_NET10모두빈값이며NET에는빈이름하나만있다. PRIMITIVE37은선택/표시설정으로배선객체가아니다. [UI증거](artifacts/project2-pcb-import.jpg).

공식KiCad가져오기문서는5.1/5.9를명시하고KiCad자체압축을권장한다(https://prodocs.easyeda.com/en/import-export/import-kicad/index.html). 최신KiCad10입력(SCH20260306/PCB20260206)과차이가있다. 원인확정은하지않는다. 추가로공개원문LAYER_PHYS에는구리/마스크등만있고유전체층이없다. 로딩완료3DUI도Board Thickness0.09mm을보여원본1.6mm대비두께손실을확인했다([3D비교화면](artifacts/project2-3d-import.jpg)). P2비교baseline을고쳐서성공으로바꾸지않았다. 별도복사본에서호환버전변환/STEP포함패키징/넷복구를시험하는것은후속항목이다.

## 영상참조 도구 v0.21.7

`/Users/denny/Project/codex-helper/tools/easyeda-agent-trial`에CLI/확장/릴리스스킬/MCP어댑터준비. CLI실행버전v0.21.7,확장manifestv0.21.7/EDA~3.2.0. releaseSHA2563개일치. annotatedtag148c409780ad212a5a9096f27a3f6bdbf52777f0가commit7dfa5f7ce8f6bd6c56f6ab493056fd49a663efcc를참조하여이전조사commit과동일. rootLICENSE파일은태그에없으나manifest와NOTICE는Apache2.0이라고명시한다. 실제 SDK stdio 초기화에서MCP 11개도구카탈로그조회성공;health는daemon미기동으로not_found(연결성공주장하지않음). MCP하위package버전0.18.3은태그내패키지메타데이터이며다른release를혼합설치하지않았다.

새확장UUID4dae27407c1d43be98e8e210d45fe587의External Interactions/127.0.0.1:60832/자동연결은사용자구체승인대기. 아직확장import/daemon연결시험하지않음. mainMCPPro프로세스는종료해한writer원칙유지. daemon사용시`--auto-update-skill=false`필수(다른클라이언트자동갱신방지). 런타임과Codex스킬링크는helper내부만가리킨다.

**트레이드오프:** 공식 API 기반의 실제 회로·PCB·3D 제어는 검증됐지만, 일부 성공 응답은 저장 지속성을 보장하지 않는다. KiCad10 가져오기는 제작에 사용할 수 없는 손실이 있어 신규 작성 결과와 구분해야 한다.
