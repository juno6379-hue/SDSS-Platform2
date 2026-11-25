# 기관 원본·검증·공개 가능성 인계

2026-11-25. `CONTINUOUS_DEVELOPMENT.md`와 이전 RTRW/CCKP/KLHK·RAG 증거를 읽고 **원격 요청0·예약추가0·원장쓰기0**으로 검증했다. 공통 API·frontend는 수정하지 않았으며 root가 mount와 UI를 담당한다.

## 읽기 전용 Python API

`services.datahub.institution_sources.build_inventory(root)`는 `institution-source-handoff/1.0` object를 반환한다. `records[]`에는 `source_id`, `verification`, `verification_scope`, `publication_gate`, `blockers`, `evidence_pins[{path,sha256,bytes}]`, 제한된 `metrics`가 있다.

`VERIFIED_REAL`은 **로컬 증거 바이트/고정 해시를 검증했다는 의미**이며 기관 승인·자료 전체·현행성 검증이 아니다. 모든 publication_gate는 BLOCKED다. 코드만으로 공개 승인을 만들지 않는다. 누락/손상 JSON, 해시 불일치, root 외부 경로는 해당 row BLOCKED로 처리한다. 예상 가능한 OSError/ValueError/KeyError/TypeError/AttributeError는 row에 예외 종류만 기록하며 private 경로나 본문을 오류에 노출하지 않는다. 잘못된 root 자체 입력과 예상하지 못한 프로그램 오류는 호출자에게 전파될 수 있으므로 HTTP 통합은 root에서 별도 처리한다.

`public_summary(inventory)`는 source_id/verification/publication_gate/public_search_enabled 및 `collection_progress_ref`만 whitelist한다. `/api/collection-progress`의 실제 datasets[].id는 rtrw/cckp/klhk/documents/sentinel이고, lake는 직접 대응 dataset이 없어 null이다. 비공개 DB 경로·청크·원문·기후 수치는 공개 summary에 포함하지 않는다. 이 함수는 인증 서비스나 승인된 RAG 검색기가 아니다.

## 실제 재검증과 미완료

| 자료 | 고정 증거에서 확인 | 별도 차단 |
|---|---|---|
| RTRW | 6주 역사 레이어93,340폴리곤·Banten역사표본1 | 현행0/6, 5주조례불일치·남동술라웨시법령검토,권리미확인 |
| CCKP | 원본4,209,592B SHA재확인, 개발bbox12,765셀 CDD40.91221481742199days | 국가행정평균/연차시계열/전체변수·기간catalog 아님,관측계열재분석·독립정답아님 |
| Lake | catalog SHA일치,6,175objects/6,721references | livePostGIS·object service cutover false, 전체 데이터 현장 재감사 아님 |
| KLHK | metadata취득7문서의 기존 verification receipt | native23검증0,2024/25renderer25와공식23domain불일치미해결·이용권리미확인 |
| 비공개 색인 | DB실제SHA일치,7문서122청크 | synthetic-hash embedding 품질미검증·private/data_steward·공개검색false |
| Sentinel | 기록8완료/5품질통과, active기록WJ2024/9번째 | RUNNING파일로프로세스생존추정금지,미정산예약보존·공간공백·독립라벨/학습별도 |

인벤토리의 KLHK 7은 KLHK 연차파일7개가 아니라 **CCKP문서5+KLHK메타데이터2**가 들어있는 기존 취득 보고서 전체 문서수다. 원본자료 숫자나 승인된 보고서 수로 해석하지 않는다. CCKP document repository의 라이선스를 기후 데이터에 전파하지 않으며 기존 공식 ERA5 카탈로그 근거를 사용한다. WorldCover2021을 타연도 독립정답으로 쓰지 않는다.

Sentinel progress는 `2026-11-25T02:50:39.950049Z` snapshot이며 completed8,quality5,추가본문50,597,002B,직전정산잔액1,627,924,028B다. 이는 9번째 pending을 포함한 현재 가용액과 다르다. 이번 read-only 원장 SHA는 `ddbeda493e3418f7d82d6430b48f5eae16a78fba3b641c22f86ceef6ca5d6d69`,new_charged2,700,597,700B/additionalmax4,294,967,296B,rate_limit_active=false였다. 차이33,554,432B를 재수집/환불하지 않았다. 전체 공간피복은 1% 미만인 기존 aggregate와 후속8창을 구분하며 이 작업에서는 재감사하지 않았다.

## 실행·증거

```powershell
python -B -m unittest discover -s tests/institution_sources -v
```

합성5시험은 누락·손상·경로이탈·해시drift·공개필드차단을 검증한다. 실서비스 성공시험과 구분한다. 로컬 실제 인벤토리는 `evidence/institution_sources/inventory-20261125.json`, 공개 축약은 `public-status-20261125.json`이다. 이전 증거를 덮어쓰거나 신규 collector·watcher를 시작하지 않았다.

다음 Gate는 현행 조례와 일치하는 RTRW원본/사용조건,KLHK공식classdomain/권리,privateindex의 실제embedding/ACL검증,기관공개승인이다. Sentinel미정산은 별도 명시된 운영 복구단위에서 처리한다. root에 API 계약/증거경로를 인계했으며 이해자료·API mount·UI적용은 root 통합과 구분한다. 커밋·푸시는 하지 않았다.
