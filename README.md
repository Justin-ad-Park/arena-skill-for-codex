# arena-skill-for-codex

Arena는 같은 문제를 여러 Codex 하위 에이전트에게 맡기고, 토너먼트로 답안을 비교하는 스킬입니다. 각 경쟁자는 추론 방식, 작업 순서, 우선순위가 다른 전략 카드를 받아 독립적으로 답합니다. 매 경기에서 두 경쟁자가 상대 답안을 비평하고 자기 답안을 수정하면, 별도의 심판이 전략 카드를 보지 않고 두 답안을 채점합니다.

## 설치

하위 에이전트 실행을 지원하는 Codex와 Python 3.8 이상이 필요합니다. 기존 Codex 로그인으로 실행되며 별도 API 키나 Python 패키지는 필요하지 않습니다.

### Codex 앱에서 채팅으로 설치

Codex 앱의 새 채팅에 아래 메시지를 붙여넣으면 설치와 2명 토너먼트 테스트를 한 번에 요청할 수 있습니다.

```text
https://github.com/Justin-ad-Park/arena-skill-for-codex 에서 Arena 플러그인을 설치해줘. 설치 후 아래 예제로 실제 토너먼트를 실행하고 우승 답안까지 확인해줘.
$arena --agents 2 비 오는 날 준비물 세 가지를 제안해줘.
```

### Codex 플러그인으로 설치

```sh
codex plugin marketplace add Justin-ad-Park/arena-skill-for-codex
codex plugin add arena@arena-for-codex
```

설치 후 새 Codex 세션에서 `$arena`를 입력하거나 스킬 목록에서 **arena**를 선택합니다. 데스크톱에서는 마켓플레이스를 추가한 뒤 **Plugins**에서 **Arena**를 설치할 수도 있습니다.

### 스킬 폴더로 설치

플러그인 명령을 사용할 수 없는 환경에서는 저장소를 내려받고 `skills/arena` 폴더 전체를 복사합니다. 아래 예시는 여러 프로젝트에서 쓰는 사용자 범위 설치입니다.

```sh
git clone https://github.com/Justin-ad-Park/arena-skill-for-codex.git
mkdir -p "$HOME/.agents/skills"
cp -R arena-skill-for-codex/skills/arena "$HOME/.agents/skills/"
```

팀 저장소에 포함하려면 복사 대상을 해당 프로젝트의 `.agents/skills/`로 바꿉니다. 플러그인과 폴더 설치 중 하나를 선택합니다. 같은 이름의 스킬을 두 곳에 설치하면 선택 목록에 중복 표시될 수 있습니다.

## 사용

아래 줄을 셸 명령이 아닌 Codex 프롬프트로 입력합니다.

```text
$arena 이 테스트가 간헐적으로 실패하는 원인과 수정안을 찾아줘.
$arena --agents 4 이 API의 페이지네이션 설계안을 비교해줘.
$arena --quick 캐시 무효화 전략을 제안해줘.
$arena --agents 16 --seed 7 --wave 4 읽기 전용 데이터 마이그레이션 계획을 검토해줘.
```

| 옵션 | 동작 |
| --- | --- |
| `--agents N` | 경쟁자 수를 2~64명으로 지정합니다. 생략하면 8명입니다. |
| `--quick` | 4명으로 실행합니다. `--agents`와 함께 쓸 수 없습니다. |
| `--seed S` | 전략 카드 배정과 대진 생성에 쓰는 난수를 고정합니다. 심판 결과에 따라 이후 대진은 달라질 수 있습니다. |
| `--wave W` | 한 번에 실행할 작업 수를 정합니다. 기본은 4이며 Codex 세션의 한도가 더 낮으면 더 작은 묶음으로 실행합니다. |
| `--report summary\|full` | 기본 `summary`는 참가자별 초안과 경기별 공격·방어·선정 요약을 보여줍니다. `full`은 수정 답안과 심판 판정 원문까지 포함합니다. |

| 경쟁자 | 라운드 | 예상 하위 에이전트 호출 |
| ---: | ---: | ---: |
| 4 | 2 | 19 |
| 8 | 3 | 43 |
| 32 | 5 | 187 |
| 64 | 6 | 379 |

호출 수에는 초안 작성, 상호 비평, 수정, 독립 심판이 포함됩니다. 기존 답안과 비교하면 심판 호출이 1회 추가되고, 실패한 작업을 재시도하면 호출 수가 늘어납니다.

경쟁자는 자기 에이전트에서 비평과 수정을 이어가고, 별도의 심판 에이전트가 경기를 차례로 평가합니다. 스레드를 닫을 수 없는 Codex 환경에서 경쟁자 4명을 실행하려면 하위 에이전트 슬롯 5개가 필요합니다. 기존 답안과 비교할 때는 우승 답안을 처음 보는 심판을 위해 슬롯이 하나 더 필요합니다. Codex가 스레드 종료를 지원하면 Arena가 완료된 슬롯을 회수해 같은 실행을 이어갑니다.

진행 상태와 답안은 작업 폴더의 `.arena/<run>/`에 저장됩니다. 중단된 실행을 이어가려면 `$arena`에 기존 실행 경로를 알려줍니다. 코드 변경은 우승 답안에 제안하고, 적용까지 요청한 경우에만 프로젝트 파일을 수정합니다. 실행 기록에는 작업 내용이 들어가므로 Git으로 추적하는 프로젝트에서는 `.arena/`를 제외할 수 있습니다.

### 요약 보고서와 전체 보고서

Arena는 최종 판정을 기다리는 동안에도 Codex 대화창에 진행 내용을 보여줍니다. 참가자별 초안은 작성이 끝나는 묶음마다 공개하고, 각 라운드에서는 공격, 방어, 선정 결과를 다음 단계로 넘어가기 전에 차례로 보여줍니다.

**요약 보고서**는 기본값입니다. `--report`를 생략하거나 `--report summary`를 지정하면 참가자별 초안과 경기별 주요 공격·방어, 점수, 진출 이유를 보여줍니다.

```text
$arena --agents 4 --report summary 이 API의 페이지네이션 설계안을 비교해줘.
```

**전체 보고서**는 `--report full`로 요청합니다. 진행 중에도 가능한 범위에서 매 경기의 공격·방어 원문, 수정 답안, 심판 판정 원문을 보여줍니다. 한 단계의 내용이 길면 대화창에 핵심을 먼저 표시하고 해당 단계의 전체 Markdown 링크를 제공합니다.

```text
$arena --agents 4 --report full 이 API의 페이지네이션 설계안을 비교해줘.
```

보고서는 참가자와 라운드별로 나눈 Markdown이며, 채팅에 다 담기 어려우면 실행 폴더에 저장된 `report-summary.md` 또는 `report-full.md` 링크가 표시됩니다. 이미 완료된 토너먼트의 전체 보고서를 보고 싶다면 아래 예시의 경로를 실제 실행 경로로 바꿔 입력하세요. 에이전트는 다시 실행되지 않습니다.

```text
$arena --report full ".arena/<run>"의 전체 보고서를 보여줘.
```

## 배포와 검증

플러그인과 직접 설치가 같은 `skills/arena/` 폴더를 사용합니다. 배포할 때는 [플러그인 매니페스트](.codex-plugin/plugin.json)의 버전을 올리고 [마켓플레이스 파일](.agents/plugins/marketplace.json), 스킬 폴더, 라이선스를 같은 Git 커밋에 포함합니다. 이 커밋이 GitHub의 기본 브랜치에 반영되면 위 설치 명령으로 받을 수 있습니다. 기존 플러그인을 업데이트하려면 `codex plugin marketplace upgrade arena-for-codex`로 저장소를 새로고침한 뒤 `codex plugin add arena@arena-for-codex`를 다시 실행합니다.

배포 전에 저장소 루트에서 다음을 확인합니다.

```sh
python3 -m unittest discover -s tests -v
python3 skills/arena/bracket.py plan
python3 skills/arena/bracket.py plan --agents 64
```

테스트는 상태 전이와 전략 배정, 심판 결과 수집을 가짜 에이전트 출력으로 검증합니다. 실제 Codex 호출은 별도로 `$arena --agents 2`로 점검할 수 있습니다.

Jake Schincariol의 [arena-skill](https://github.com/Jakeschincariol/arena-skill/tree/df07b8e518e10cdecd8cd7712d9958b6f396250e)을 Codex로 이식했습니다. [MIT 라이선스](LICENSE)를 따릅니다.
