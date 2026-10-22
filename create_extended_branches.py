import os
import json

base_dir = os.path.dirname(__file__)

def make_ai_studio_json(title, chunks, sys_prompt="AI Studio Assistant"):
    return {
        "runSettings": {
            "temperature": 0.7,
            "model": "models/gemini-2.5-pro",
            "topP": 0.95,
            "topK": 64,
            "maxOutputTokens": 8192
        },
        "systemInstruction": {
            "text": sys_prompt
        },
        "chunkedPrompt": {
            "chunks": chunks
        }
    }

# ==========================================
# 1. 세계관 1: SF 화성 탐사 (기존 1~3차 분기 + 4차, 5차 분기 추가)
# ==========================================
sf_dir = os.path.join(base_dir, 'storage', '테스트_탐사')
os.makedirs(sf_dir, exist_ok=True)

c0 = { "role": "user", "text": "화성 기지 7구역에서 미확인 지하 음향 신호가 감지되었습니다. 신호 패턴을 분석하고 1차 탐사 계획을 수립하세요.", "tokenCount": 24 }
c1 = { "role": "model", "isThought": True, "text": "음향 주파수 스펙트럼을 분석하여 지질학적 진동인지 인공 신호인지 판별한다. 탐사 로봇 및 센서 배치를 검토한다.", "parts": [{"text": "음향 주파수 스펙트럼 분석 중...", "thought": True}], "tokenCount": 35 }
c2 = { "role": "model", "text": "주파수 분석 결과: 규칙적인 3.8Hz 펄스 신호로 인공 구조물의 공명 현상일 가능성이 높습니다. 입구 좌표(34.2N, 12.8W)로 정찰을 추천합니다.", "tokenCount": 42 }
c3 = { "role": "user", "text": "알겠습니다. 정찰 로봇 알파를 입구로 출동시켰습니다.", "tokenCount": 16 }

c4_a = { "role": "model", "text": "로봇 알파가 지하 50m 지점에 진입했습니다. 암벽에 고대 외계 문명으로 추정되는 발광 벽화를 발견했습니다.", "tokenCount": 38 }
c5_a = { "role": "user", "text": "벽화의 문양을 고해상도로 스캔하고 텍스트 번역을 시도하세요.", "tokenCount": 20 }

c4_b = { "role": "model", "text": "지하 동굴의 지반이 불안정하여 안전을 위해 지상에서 지중 레이다(GPR) 원격 스캔을 우선 가동했습니다.", "tokenCount": 35 }

c6 = { "role": "model", "text": "벽화 스캔 번역 결과, '영원의 불꽃'이라 명명된 구형 에너지 코어의 보관 장소로 확인되었습니다. 제단 중앙에서 코어를 발견했습니다!", "tokenCount": 45 }
c7 = { "role": "user", "text": "코어의 에너지 방출량과 방사능 수치를 측정하세요.", "tokenCount": 18 }

c8 = { "role": "model", "text": "방사능은 제로입니다. 코어 주변 반경 5m 내에서 중력이 40% 감소하는 반중력 역장이 관측되었습니다.", "tokenCount": 36 }
c9 = { "role": "user", "text": "기지의 이동형 리프트에 코어를 장착하여 반중력 추진 시험을 실시하겠습니다.", "tokenCount": 24 }

# 4차 분기 추가 (05번에서 이어짐: 워프 드라이브 시험)
c10 = { "role": "model", "text": "반중력 추진체의 출력이 정상 궤도에 올랐습니다. 시공간 곡률 왜곡 수치가 안정적인 워프 항법을 가리키고 있습니다.", "tokenCount": 40 }
c11 = { "role": "user", "text": "탐사선 '아르고스'에 코어를 탑재하고 광속 10% 시험 도약을 승인합니다.", "tokenCount": 22 }

# 5차 분기 추가 (06번에서 이어짐: 미지 성계 도달)
c12 = { "role": "model", "text": "성공적으로 워프 도약을 완료했습니다! 태양계 외곽 0.5광년 거리의 미탐사 소행성대 중심부에 진입했습니다.", "tokenCount": 42 }
c13 = { "role": "user", "text": "소행성대 표면의 에너지 반응을 전면 스캔하고 귀환 좌표를 확보하세요.", "tokenCount": 20 }

# 4차 분기 파일 저장
chunks_f6 = [c0, c1, c2, c3, c4_a, c5_a, c6, c7, c8, c9, c10, c11]
with open(os.path.join(sf_dir, '06_워프추진시험_4차연쇄분기.json'), 'w', encoding='utf-8') as f:
    json.dump(make_ai_studio_json('06_워프추진시험_4차연쇄분기', chunks_f6, "화성 탐사 기지 메인 컴퓨터"), f, ensure_ascii=False, indent=2)

# 5차 분기 파일 저장
chunks_f7 = [c0, c1, c2, c3, c4_a, c5_a, c6, c7, c8, c9, c10, c11, c12, c13]
with open(os.path.join(sf_dir, '07_미지성계도달_5차심층분기.json'), 'w', encoding='utf-8') as f:
    json.dump(make_ai_studio_json('07_미지성계도달_5차심층분기', chunks_f7, "화성 탐사 기지 메인 컴퓨터"), f, ensure_ascii=False, indent=2)

# ==========================================
# 2. 세계관 2: 판타지 제국 (독립된 또 다른 세계관 상위 분류!)
# ==========================================
fantasy_dir = os.path.join(base_dir, 'storage', '판타지_세계관')
os.makedirs(fantasy_dir, exist_ok=True)

p0 = { "role": "user", "text": "제국 수도의 대도서관 지하 서고에서 잊혀진 고대 마법서가 발견되었습니다. 서책의 봉인을 확인하세요.", "tokenCount": 28 }
p1 = { "role": "model", "isThought": True, "text": "마법서에 걸린 금제 주문의 계열과 마력 잔여량을 측정한다. 저주나 함정의 유무를 감별한다.", "parts": [{"text": "금제 주문 계열 감별 중...", "thought": True}], "tokenCount": 32 }
p2 = { "role": "model", "text": "서책 표면에 7중 사슬 결계가 걸려 있습니다. 제3대 대마법사의 인장이 희미하게 빛나고 있습니다.", "tokenCount": 36 }

# 판타지 Root Trunk (청크 3개)
with open(os.path.join(fantasy_dir, '01_대도서관_고문서_원본Trunk.json'), 'w', encoding='utf-8') as f:
    json.dump(make_ai_studio_json('01_대도서관_고문서_원본Trunk', [p0, p1, p2], "아르카디아 제국 궁정 마법사 기록관"), f, ensure_ascii=False, indent=2)

# 판타지 1차 분기 (청크 5개)
p3 = { "role": "user", "text": "해독 마법을 사용하여 첫 번째 사슬 결계를 해제하겠습니다.", "tokenCount": 18 }
p4 = { "role": "model", "text": "첫 번째 사슬이 풀리면서 서책이 푸른 안개를 내뿜기 시작했습니다. 고대 정령어 문장이 드러났습니다.", "tokenCount": 34 }
with open(os.path.join(fantasy_dir, '02_결계해제_1차분기.json'), 'w', encoding='utf-8') as f:
    json.dump(make_ai_studio_json('02_결계해제_1차분기', [p0, p1, p2, p3, p4], "아르카디아 제국 궁정 마법사 기록관"), f, ensure_ascii=False, indent=2)

# 판타지 2차 연쇄 분기 (청크 7개)
p5 = { "role": "user", "text": "고대 정령어 문장을 해독하여 봉인된 마수의 이름을 확인하세요.", "tokenCount": 20 }
p6 = { "role": "model", "text": "해독 결과, 빙결의 군주 '프로스트팽'의 영혼이 서책 속에 봉인되어 있습니다! 즉시 결계를 재강화해야 합니다.", "tokenCount": 38 }
with open(os.path.join(fantasy_dir, '03_마수봉인확인_2차연쇄분기.json'), 'w', encoding='utf-8') as f:
    json.dump(make_ai_studio_json('03_마수봉인확인_2차연쇄분기', [p0, p1, p2, p3, p4, p5, p6], "아르카디아 제국 궁정 마법사 기록관"), f, ensure_ascii=False, indent=2)

print("Created 4th/5th depth branches and new Fantasy Worldview files successfully!")
