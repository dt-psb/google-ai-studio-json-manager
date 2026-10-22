import os
import json

base_dir = os.path.join(os.path.dirname(__file__), 'storage', '테스트_탐사')
os.makedirs(base_dir, exist_ok=True)

def make_ai_studio_json(title, chunks, sys_prompt="화성 탐사 기지 메인 컴퓨터 제어 시스템"):
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

c0 = {
    "role": "user",
    "text": "화성 기지 7구역에서 미확인 지하 음향 신호가 감지되었습니다. 신호 패턴을 분석하고 1차 탐사 계획을 수립하세요.",
    "tokenCount": 24
}
c1 = {
    "role": "model",
    "isThought": True,
    "text": "음향 주파수 스펙트럼을 분석하여 지질학적 진동인지 인공 신호인지 판별한다. 탐사 로봇 및 센서 배치를 검토한다.",
    "parts": [{"text": "음향 주파수 스펙트럼 분석 중...", "thought": True}],
    "tokenCount": 35
}
c2 = {
    "role": "model",
    "text": "주파수 분석 결과: 규칙적인 3.8Hz 펄스 신호로 인공 구조물의 공명 현상일 가능성이 높습니다. 입구 좌표(34.2N, 12.8W)로 정찰을 추천합니다.",
    "tokenCount": 42
}
c3 = {
    "role": "user",
    "text": "알겠습니다. 정찰 로봇 알파를 입구로 출동시켰습니다.",
    "tokenCount": 16
}

# 1. 원본 Root Trunk
chunks_f1 = [c0, c1, c2, c3]
f1_path = os.path.join(base_dir, '01_화성기지_최초교신_원본Trunk.json')
with open(f1_path, 'w', encoding='utf-8') as f:
    json.dump(make_ai_studio_json('01_화성기지_최초교신_원본Trunk', chunks_f1), f, ensure_ascii=False, indent=2)

# 2. 1차 분기 A (지하 탐사)
c4_a = {
    "role": "model",
    "text": "로봇 알파가 지하 50m 지점에 진입했습니다. 암벽에 고대 외계 문명으로 추정되는 발광 벽화를 발견했습니다.",
    "tokenCount": 38
}
c5_a = {
    "role": "user",
    "text": "벽화의 문양을 고해상도로 스캔하고 텍스트 번역을 시도하세요.",
    "tokenCount": 20
}
chunks_f2 = [c0, c1, c2, c3, c4_a, c5_a]
f2_path = os.path.join(base_dir, '02_탐사로봇_1차분기_지하탐사.json')
with open(f2_path, 'w', encoding='utf-8') as f:
    json.dump(make_ai_studio_json('02_탐사로봇_1차분기_지하탐사', chunks_f2), f, ensure_ascii=False, indent=2)

# 3. 1차 분기 B (지상 대기 및 원격 스캔)
c4_b = {
    "role": "model",
    "text": "지하 동굴의 지반이 불안정하여 안전을 위해 지상에서 지중 레이다(GPR) 원격 스캔을 우선 가동했습니다.",
    "tokenCount": 35
}
chunks_f3 = [c0, c1, c2, c3, c4_b]
f3_path = os.path.join(base_dir, '03_탐사로봇_1차분기_지상원격스캔.json')
with open(f3_path, 'w', encoding='utf-8') as f:
    json.dump(make_ai_studio_json('03_탐사로봇_1차분기_지상원격스캔', chunks_f3), f, ensure_ascii=False, indent=2)

# 4. 2차 연쇄 분기 (02번에서 추가 분기: 고대 에너지 코어 발굴)
c6 = {
    "role": "model",
    "text": "벽화 스캔 번역 결과, '영원의 불꽃'이라 명명된 구형 에너지 코어의 보관 장소로 확인되었습니다. 제단 중앙에서 코어를 발견했습니다!",
    "tokenCount": 45
}
c7 = {
    "role": "user",
    "text": "코어의 에너지 방출량과 방사능 수치를 측정하세요.",
    "tokenCount": 18
}
chunks_f4 = [c0, c1, c2, c3, c4_a, c5_a, c6, c7]
f4_path = os.path.join(base_dir, '04_지하탐사_2차연쇄분기_에너지코어.json')
with open(f4_path, 'w', encoding='utf-8') as f:
    json.dump(make_ai_studio_json('04_지하탐사_2차연쇄분기_에너지코어', chunks_f4), f, ensure_ascii=False, indent=2)

# 5. 3차 심층 분기 (04번에서 추가 분기: 반중력장 활성화)
c8 = {
    "role": "model",
    "text": "방사능은 제로입니다. 코어 주변 반경 5m 내에서 중력이 40% 감소하는 반중력 역장이 관측되었습니다.",
    "tokenCount": 36
}
c9 = {
    "role": "user",
    "text": "기지의 이동형 리프트에 코어를 장착하여 반중력 추진 시험을 실시하겠습니다.",
    "tokenCount": 24
}
chunks_f5 = [c0, c1, c2, c3, c4_a, c5_a, c6, c7, c8, c9]
f5_path = os.path.join(base_dir, '05_에너지코어_3차심층분기_반중력시험.json')
with open(f5_path, 'w', encoding='utf-8') as f:
    json.dump(make_ai_studio_json('05_에너지코어_3차심층분기_반중력시험', chunks_f5), f, ensure_ascii=False, indent=2)

print("Created 5 sample AI Studio branch files in storage/테스트_탐사/ successfully!")
