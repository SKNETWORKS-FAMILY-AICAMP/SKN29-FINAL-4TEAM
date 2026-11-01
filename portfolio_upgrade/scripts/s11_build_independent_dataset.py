"""S11: original fictional, condition-grounded training candidates.

From a repository root:
    python portfolio_upgrade/scripts/s11_build_independent_dataset.py --check
    python portfolio_upgrade/scripts/s11_build_independent_dataset.py --write

NO imported SKMagic/WaterBridge manuals, S07, S08, old Holdout, embedding
models, model weights, GPU, API, or connectors. This is an original simulation.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "portfolio_upgrade/data/s11_grounded"
REPORT = ROOT / "portfolio_upgrade/experiments/s11_readiness"
ACTIONS = ("ANSWER", "ASK", "ESCALATE", "EXPLAIN_UNSUPPORTED")
SYS_PROMPT = """당신은 가상 제품 SIM 시리즈의 고객지원 응대 실습 모델입니다. 제공된 가상 정책 근거와 제품 코드, 고객이 이미 확인한 조건만 사용하십시오. 가장 관련 있는 근거의 적용 조건을 확인해 ANSWER, ASK, ESCALATE, EXPLAIN_UNSUPPORTED 중 하나를 선택하십시오. 위험 징후가 명시되면 다른 사용법보다 ESCALATE를 우선합니다. 조건이 빠졌으면 추측하지 말고 ASK를 선택합니다. 없는 기능은 해당 제품 근거가 명시적으로 지원하지 않는다고 할 때만 EXPLAIN_UNSUPPORTED로 설명합니다. 다른 조건의 근거를 잘못 인용하지 마세요. 고객이 수행하지 않은 조치를 완료했다고 말하지 마세요. 출력은 코드블록 없이 유효한 JSON 객체 하나만 작성하며 정확히 action, customer_message, cited_evidence_ids, missing_fields 네 필드를 포함해야 합니다. 배열이 비어도 필드를 생략하지 마세요. 출력 뒤에 다른 글을 덧붙이지 마세요."""

# Every rule/question/answer below is written for this fictional exercise.
# Each device/topic family stays entirely in ONE split. Every family covers
# all four actions with separate, condition-specific policy and a distractor.
# Fields: customer question, source rule, grounded response, missing field.
FAMILIES = [
    {
        "id":"F01", "product":"SIM-L01", "name":"연습용 책상 조명", "topic":"조명 표시와 밝기",
        "A":("파란 점이 두 번 깜빡이는데 불이 고장 난 건가요?", "SIM-L01에서 파란 점이 두 번 깜빡이는 것은 연결 대기 상태다. 연결을 시작하려면 본체의 확인 버튼을 한 번 누른다.", "파란 점 두 번 깜빡임은 연결 대기 상태입니다. 연결하려면 본체의 확인 버튼을 한 번 눌러 주세요."),
        "Q":("밝기가 자꾸 변해요. 어떻게 바꾸나요?", "SIM-L01의 밝기 변화는 자동 밝기 모드와 수동 밝기 모드에 따라 확인 절차가 다르다. 먼저 현재 밝기 모드를 확인해야 한다.", "현재 밝기 모드가 자동인가요, 수동인가요?", "brightness_mode"),
        "E":("조명 밝기를 올리려는데 어댑터 연결부에서 타는 냄새가 나요.", "SIM-L01의 전원 연결부에서 타는 냄새가 나면 밝기 조작을 중단하고 사용을 멈춘 뒤 안전하게 접근할 수 있을 때 전원을 차단하고 지원센터에 문의한다.", "밝기 조작을 중단하고 사용을 멈춰 주세요. 안전하게 접근할 수 있다면 전원을 차단하고 지원센터에 문의해 주세요."),
        "U":("이 조명으로 사람을 카메라로 따라가며 비출 수 있나요?", "SIM-L01은 카메라가 없으며 사람 추적 조명 기능을 제공하지 않는다.", "SIM-L01은 카메라와 사람 추적 조명 기능을 지원하지 않습니다."),
    },
    {
        "id":"F02", "product":"SIM-H02", "name":"연습용 습도 알림기", "topic":"습도·물통 상태",
        "A":("초록 링이 천천히 깜빡여요. 측정이 멈춘 건가요?", "SIM-H02에서 초록 링의 느린 점멸은 실내 습도 측정을 준비하는 정상 상태다. 측정값을 바로 보려면 화면 버튼을 한 번 누른다.", "초록 링의 느린 점멸은 측정 준비 상태입니다. 화면 버튼을 한 번 누르면 측정값을 볼 수 있습니다."),
        "Q":("습도가 너무 높다고 뜨는데 알림을 어떻게 맞춰요?", "SIM-H02의 고습도 알림 설정은 주거 모드와 저장 모드에 따라 조절법이 다르다. 활성화된 알림 모드를 먼저 확인한다.", "현재 알림 모드가 주거 모드인가요, 저장 모드인가요?", "humidity_alert_mode"),
        "E":("기기를 옮기다가 전자부 안으로 물이 들어갔어요. 계속 켜도 되나요?", "SIM-H02 전자부에 물이 유입되었으면 전원을 켜거나 작동을 재개하지 않고 사용을 중단하며 지원센터 점검을 요청한다.", "전자부에 물이 들어갔다면 작동을 재개하지 말고 사용을 중단한 뒤 지원센터에 점검을 요청해 주세요."),
        "U":("이 알림기로 실내 공기를 자동 가습할 수 있나요?", "SIM-H02는 습도 표시와 알림만 제공한다. 가습 기능과 물 분사 기능은 지원하지 않는다.", "SIM-H02는 습도 표시·알림 장치이며 자동 가습이나 물 분사를 지원하지 않습니다."),
    },
    {
        "id":"F03", "product":"SIM-F03", "name":"연습용 소형 순환 팬", "topic":"풍량·회전",
        "A":("흰 바람개비 표시가 켜져 있고 바람이 약해요. 정상인가요?", "SIM-F03에서 흰 바람개비 표시는 저소음 풍량 모드를 뜻한다. 풍량을 한 단계 올리려면 바람 버튼을 짧게 한 번 누른다.", "흰 바람개비 표시는 저소음 모드입니다. 바람 버튼을 짧게 한 번 눌러 풍량을 한 단계 올릴 수 있습니다."),
        "Q":("바람 방향이 움직이지 않는데 설정이 뭐가 문제죠?", "SIM-F03 회전 진단은 회전 잠금 스위치가 잠김인지 풀림인지에 따라 달라진다. 먼저 스위치 위치를 확인한다.", "회전 잠금 스위치가 현재 잠김인가요, 풀림인가요?", "rotation_lock_state"),
        "E":("팬에서 연기가 조금 나는데 회전 버튼을 눌러 봐도 될까요?", "SIM-F03에서 연기나 연소 냄새가 나면 회전·풍량 버튼을 누르지 않고 사용을 멈춘 후 접근이 안전하면 전원을 끄고 점검을 요청한다.", "버튼을 더 누르지 말고 사용을 멈춰 주세요. 안전하게 할 수 있다면 전원을 끄고 지원센터에 점검을 요청해 주세요."),
        "U":("팬이 방 안을 알아서 이동하며 청소도 하나요?", "SIM-F03은 고정형 순환 팬이다. 바닥 이동 및 청소 기능을 지원하지 않는다.", "SIM-F03은 고정형 팬으로 자동 이동이나 청소 기능을 지원하지 않습니다."),
    },
    {
        "id":"F04", "product":"SIM-P04", "name":"연습용 휴대용 스피커", "topic":"음향 입력·연결",
        "A":("연결등이 청록색으로 고정됐는데 음악이 안 나와요. 어떤 상태예요?", "SIM-P04의 청록색 고정등은 블루투스 연결 완료를 뜻한다. 연결 후 소리가 작으면 본체 볼륨 버튼을 한 번 눌러 음량 표시를 확인할 수 있다.", "청록색 고정등은 블루투스 연결 완료입니다. 본체 볼륨 버튼을 눌러 음량 표시를 확인해 주세요."),
        "Q":("외부 기기 소리가 안 나오는데 무엇부터 확인하죠?", "SIM-P04의 외부 소리 입력 경로는 블루투스와 유선 입력에서 다르다. 먼저 현재 선택한 입력 소스를 확인해야 한다.", "입력 소스를 블루투스로 선택하셨나요, 유선 입력으로 선택하셨나요?", "audio_input_source"),
        "E":("충전 중에 스피커 외관이 부풀어 올랐어요. 재생해도 돼요?", "SIM-P04의 배터리 부풀음은 위험 징후다. 충전·재생을 즉시 중지하고 장치를 건드리거나 분해하지 않으며 지원센터에 문의한다.", "충전과 재생을 즉시 중단하고 장치를 분해하거나 계속 사용하지 마세요. 지원센터에 문의해 주세요."),
        "U":("스피커가 내 통화 내용을 자체적으로 녹음해 저장하나요?", "SIM-P04에는 통화 녹음 및 내부 통화 기록 저장 기능이 없다.", "SIM-P04는 통화 녹음과 통화 기록 저장 기능을 지원하지 않습니다."),
    },
    {
        "id":"F05", "product":"SIM-C05", "name":"연습용 디지털 탁상 시계", "topic":"시각 표시·동기화",
        "A":("시계 오른쪽에 작은 달 그림이 떠요. 시간 설정이 잘못됐나요?", "SIM-C05의 달 아이콘은 야간 표시 모드가 켜졌다는 뜻이다. 야간 표시를 해제하려면 디스플레이 버튼을 한 번 누른다.", "달 아이콘은 야간 표시 모드입니다. 디스플레이 버튼을 한 번 누르면 해제됩니다."),
        "Q":("시계 시간이 한 시간씩 달라져요. 어떻게 고쳐요?", "SIM-C05의 시간 차이 조정은 자동 시각 동기화 사용 여부에 따라 달라진다. 조치 전 자동 동기화 상태를 확인해야 한다.", "자동 시각 동기화가 켜져 있나요, 꺼져 있나요?", "automatic_time_sync"),
        "E":("시계 전원 케이블이 찢어졌는데 알람은 계속 써도 될까요?", "SIM-C05의 전원 케이블 피복이 손상된 경우 사용을 중단하고 손상된 케이블로 전원을 공급하지 않으며 지원센터에 문의한다.", "손상된 케이블로 시계를 계속 사용하지 말고 전원 공급을 중단한 뒤 지원센터에 문의해 주세요."),
        "U":("이 시계로 GPS 위치 추적도 할 수 있나요?", "SIM-C05는 탁상 시각 표시 전용이며 GPS 위치 추적 기능을 제공하지 않는다.", "SIM-C05는 GPS 위치 추적 기능을 지원하지 않습니다."),
    },
    {
        "id":"F06", "product":"SIM-W06", "name":"연습용 화분 급수 알림기", "topic":"토양 알림·상태",
        "A":("화분 알림기에서 하늘색 한 줄이 움직입니다. 무슨 뜻인가요?", "SIM-W06에서 하늘색 막대 한 줄이 움직이면 토양 상태를 읽는 정상 과정이다. 현재 값을 보려면 읽기 버튼을 한 번 누른다.", "하늘색 막대 움직임은 토양 상태를 읽는 과정입니다. 읽기 버튼을 눌러 현재 값을 볼 수 있습니다."),
        "Q":("토양 건조 경고가 계속 뜹니다. 기준을 바꿀까요?", "SIM-W06의 건조 경고 기준은 관엽 모드와 다육 모드에서 다르다. 먼저 선택한 식물 모드를 확인해야 한다.", "식물 모드가 관엽 모드인가요, 다육 모드인가요?", "plant_profile"),
        "E":("센서 케이스에 금이 가서 전선이 보이는데 화분에 계속 꽂아도 될까요?", "SIM-W06 센서 케이스가 깨져 내부 전선이 노출되면 급수 알림 기능을 계속 사용하지 말고 장치를 분리해 지원센터에 문의한다. 젖은 상태에서는 전선에 손대지 않는다.", "센서 사용을 중단하고 젖은 상태에서 노출된 전선에 손대지 마세요. 안전이 확보된 뒤 지원센터에 문의해 주세요."),
        "U":("이 제품이 물을 직접 펌프로 공급해 주나요?", "SIM-W06은 물을 공급하는 펌프가 없는 토양 알림 전용 장치다. 자동 급수 기능을 지원하지 않는다.", "SIM-W06은 토양 상태 알림 장치이며 물 펌프나 자동 급수 기능을 지원하지 않습니다."),
    },
    {
        "id":"F07", "product":"SIM-K07", "name":"연습용 무선 키패드", "topic":"키 입력·모드",
        "A":("키패드에 노란 자물쇠가 계속 떠요. 왜 숫자가 안 눌리죠?", "SIM-K07에서 노란 자물쇠 아이콘은 숫자 잠금 모드를 의미한다. 숫자 모드를 전환하려면 Num 버튼을 짧게 누른다.", "노란 자물쇠는 숫자 잠금 모드입니다. Num 버튼을 짧게 눌러 숫자 모드를 전환해 보세요."),
        "Q":("특수키가 다른 문자로 입력됩니다. 무슨 설정을 봐야 하죠?", "SIM-K07의 특수키 해석은 PC 입력 레이아웃 선택에 따라 달라진다. 먼저 한국어 레이아웃인지 영문 레이아웃인지 확인한다.", "현재 입력 레이아웃을 한국어로 선택하셨나요, 영문으로 선택하셨나요?", "keyboard_layout"),
        "E":("키패드 건전지 칸에서 액체가 새는데 계속 연결해도 되나요?", "SIM-K07 배터리실에 누액이 발생하면 사용을 중단하고 누액을 직접 만지지 않으며 지원센터에 안전한 처리 방법을 문의한다.", "사용을 중단하고 누출된 액체를 직접 만지지 마세요. 지원센터에 안전한 처리 절차를 문의해 주세요."),
        "U":("키패드로 지문 인증도 받을 수 있나요?", "SIM-K07은 숫자·문자 입력 전용 키패드이며 지문 센서와 지문 인증 기능이 없다.", "SIM-K07에는 지문 센서가 없어 지문 인증을 지원하지 않습니다."),
    },
    {
        "id":"F08", "product":"SIM-A08", "name":"연습용 실내 공기 표시기", "topic":"공기센서·교정",
        "A":("공기 표시기 테두리가 보라색으로 돌아가요. 고장인가요?", "SIM-A08의 회전하는 보라색 테두리는 센서 영점 확인 중임을 뜻한다. 상태를 확인하려면 상태 버튼을 한 번 눌러 진행 표시를 연다.", "보라색 테두리 회전은 센서 영점 확인 중이라는 뜻입니다. 상태 버튼을 눌러 진행 표시를 확인해 주세요."),
        "Q":("측정 수치가 흔들리는데 교정을 다시 해야 하나요?", "SIM-A08 수치 변동은 이동 직후와 고정 설치 상태에서 확인 방식이 다르다. 먼저 기기를 최근에 옮겼는지 확인해야 한다.", "기기를 최근에 다른 위치로 옮기셨나요, 아니면 같은 위치에 두고 계셨나요?", "recent_relocation"),
        "E":("표시기 안에서 탁 소리 후 전원부에 불꽃이 보였어요.", "SIM-A08 내부에서 불꽃이 관찰되면 장치 조작을 즉시 중단하고 안전거리를 유지하며 지원센터에 점검을 요청한다.", "장치를 더 조작하지 말고 안전거리를 유지해 주세요. 지원센터에 점검을 요청해 주세요."),
        "U":("공기 표시기에 카메라가 있어서 얼굴을 인식하나요?", "SIM-A08은 공기 상태 측정·표시 전용 제품이며 카메라·얼굴 인식 기능이 없다.", "SIM-A08은 카메라나 얼굴 인식 기능을 지원하지 않습니다."),
    },
    {
        "id":"F09", "product":"SIM-R09", "name":"연습용 이동 청소기", "topic":"청소 경로·도킹",
        "A":("청소기가 도킹 후 파란 바가 왔다 갔다 해요. 무슨 표시인가요?", "SIM-R09의 도킹 후 파란 바 왕복은 충전 접점 확인 상태다. 충전 진행을 확인하려면 본체 상태 버튼을 한 번 누른다.", "파란 바가 왕복하는 것은 충전 접점 확인 상태입니다. 본체 상태 버튼으로 충전 진행을 확인할 수 있습니다."),
        "Q":("청소기가 문 앞에서 자꾸 멈춥니다. 어떤 모드로 설정해야 할까요?", "SIM-R09의 문턱 정지 점검은 카펫 모드와 일반 바닥 모드에 따라 달라진다. 현재 바닥 모드를 먼저 확인해야 한다.", "바닥 모드가 카펫인가요, 일반 바닥인가요?", "floor_mode"),
        "E":("충전 중 청소기 배터리 부분에서 연기가 납니다. 청소를 다시 시작할까요?", "SIM-R09 배터리에서 연기가 보이면 충전과 청소를 즉시 중단하고 장치에 가까이 가지 않으며 안전한 곳에서 지원센터에 연락한다.", "충전과 청소를 즉시 중단하고 기기에서 거리를 유지해 주세요. 안전한 곳에서 지원센터에 연락해 주세요."),
        "U":("청소기에 걸레 자동 세탁 기능도 있나요?", "SIM-R09는 흡입 청소 전용이며 걸레 자동 세탁 장치를 지원하지 않는다.", "SIM-R09는 걸레 자동 세탁 기능을 지원하지 않습니다."),
    },
    {
        "id":"F10", "product":"SIM-D10", "name":"연습용 탁상 정보 패널", "topic":"정보 패널·화면",
        "A":("정보 패널 오른쪽 위에 회색 동그라미가 떠요. 업데이트가 안 된 건가요?", "SIM-D10의 회색 원은 오프라인 보기 모드를 뜻한다. 저장된 화면을 새로 보려면 새로고침 버튼을 한 번 누른다.", "회색 원은 오프라인 보기 모드입니다. 새로고침 버튼을 눌러 저장된 화면을 다시 표시할 수 있습니다."),
        "Q":("화면 글씨가 잘려 보입니다. 어떤 설정을 바꿔야 할까요?", "SIM-D10에서 글자 잘림 점검은 세로 배치와 가로 배치에서 조절 메뉴가 다르다. 현재 배치 방향을 확인해야 한다.", "정보 패널을 세로로 놓으셨나요, 가로로 놓으셨나요?", "panel_orientation"),
        "E":("화면 가장자리에서 지지직 소리와 탄 냄새가 납니다.", "SIM-D10에서 전기 잡음과 탄 냄새가 동시에 나면 화면 설정을 바꾸지 말고 사용을 중지하며 안전한 경우 전원을 차단한 뒤 지원센터에 문의한다.", "설정을 더 바꾸지 말고 사용을 중지해 주세요. 안전하게 가능하면 전원을 차단하고 지원센터에 문의해 주세요."),
        "U":("이 패널에서 지문을 등록해 출입문을 열 수 있나요?", "SIM-D10은 정보 표시 장치로 지문 등록 및 출입문 잠금 제어 기능을 제공하지 않는다.", "SIM-D10은 지문 등록이나 출입문 잠금 제어를 지원하지 않습니다."),
    },
    {
        "id":"F11", "product":"SIM-S11", "name":"연습용 책상 스캐너", "topic":"스캔 설정·급지",
        "A":("스캐너에 파란 문서 두 장 표시가 떠요. 두 번 스캔되는 건가요?", "SIM-S11의 파란 문서 두 장 아이콘은 연속 스캔 대기 모드다. 한 장만 스캔하려면 단일 스캔 버튼을 누른다.", "파란 문서 두 장은 연속 스캔 대기 표시입니다. 한 장만 스캔하려면 단일 스캔 버튼을 눌러 주세요."),
        "Q":("스캔한 문서 가장자리가 잘립니다. 용지 설정이 문제인가요?", "SIM-S11의 테두리 잘림 조치는 자동 크기 감지와 수동 크기 설정에 따라 다르다. 현재 용지 크기 모드를 먼저 확인한다.", "용지 크기를 자동 감지로 두셨나요, 수동으로 지정하셨나요?", "paper_size_mode"),
        "E":("급지기 안에 종이가 끼었는데 전선 피복도 벗겨져 있어요. 뽑아도 되나요?", "SIM-S11 급지기 내부에 전선 피복 손상이 보이면 손이나 도구를 내부에 넣지 말고 사용을 중단해 지원센터 점검을 요청한다.", "급지기 내부에 손이나 도구를 넣지 말고 사용을 중단해 주세요. 지원센터에 점검을 요청해 주세요."),
        "U":("스캐너가 종이를 자동으로 파쇄해 주나요?", "SIM-S11은 문서 이미지 스캔 전용이며 자동 파쇄 기능이 없다.", "SIM-S11은 종이 자동 파쇄 기능을 지원하지 않습니다."),
    },
    {
        "id":"F12", "product":"SIM-T12", "name":"연습용 온도 보관 상자", "topic":"보관 온도·운전",
        "A":("온도 상자에 하얀 눈송이 대신 파란 선이 켜져요. 이게 뭔가요?", "SIM-T12의 파란 가로선은 온도 안정화 대기 상태를 의미한다. 현재 설정 온도를 보려면 정보 버튼을 한 번 누른다.", "파란 가로선은 온도 안정화 대기 상태입니다. 정보 버튼으로 설정 온도를 확인할 수 있습니다."),
        "Q":("상자가 설정한 온도로 잘 안 맞춰져요. 바로 조절할까요?", "SIM-T12의 온도 불일치 점검은 뚜껑이 닫혀 있는지 열린 상태인지에 따라 다르다. 먼저 뚜껑 상태를 확인한다.", "현재 뚜껑이 완전히 닫혀 있나요, 열려 있나요?", "lid_closed"),
        "E":("보관 상자 안에서 심한 탄 냄새가 나는데 온도를 더 올릴까요?", "SIM-T12에서 내부 탄 냄새가 심하면 설정 온도를 올리지 않고 사용을 중단하고 안전한 상태에서 전원을 차단해 지원센터에 문의한다.", "온도를 더 올리지 말고 사용을 중단해 주세요. 안전한 상태에서 전원을 차단하고 지원센터에 문의해 주세요."),
        "U":("이 상자에서 음식을 자동으로 튀길 수도 있나요?", "SIM-T12는 온도 상태를 유지하는 보관 전용 상자다. 기름 조리 및 튀김 기능을 지원하지 않는다.", "SIM-T12는 튀김이나 기름 조리 기능을 지원하지 않습니다."),
    },
    # Probe-only families. Their entire topics and product codes are absent from Train.
    {
        "id":"F13", "product":"SIM-B13", "name":"연습용 가방 위치 태그", "topic":"위치 태그·알림",
        "A":("태그에 주황 점이 한 번씩 켜집니다. 배터리 경고인가요?", "SIM-B13의 주황 점 단일 점멸은 근거리 탐색 대기 상태다. 태그 찾기 소리를 켜려면 찾기 버튼을 짧게 누른다.", "주황 점 한 번 점멸은 근거리 탐색 대기입니다. 찾기 버튼을 짧게 눌러 소리를 켜 보세요."),
        "Q":("가방이 멀어졌다는 알림이 안 떠요. 무엇을 확인할까요?", "SIM-B13의 거리 알림 진단은 실내 탐색과 실외 탐색 설정이 다르므로 현재 탐색 모드를 먼저 확인해야 한다.", "현재 탐색 모드가 실내인가요, 실외인가요?", "tracking_mode"),
        "E":("태그 배터리 커버가 뜨겁고 변형됐어요. 다시 가방에 달아도 되나요?", "SIM-B13 배터리 커버의 과열·변형은 위험 신호다. 태그 사용을 중단하고 직접 분해하지 않으며 지원센터에 문의한다.", "태그 사용을 중단하고 분해하지 말아 주세요. 지원센터에 안전한 점검을 문의해 주세요."),
        "U":("태그에 카메라가 있어서 가방 주변 사진을 찍을 수 있나요?", "SIM-B13에는 카메라가 없으며 사진 촬영 기능을 제공하지 않는다.", "SIM-B13은 카메라나 사진 촬영 기능을 지원하지 않습니다."),
    },
    {
        "id":"F14", "product":"SIM-M14", "name":"연습용 책장 진동 감시기", "topic":"진동 이벤트·부착",
        "A":("진동 감시기에 초록 잎 표시가 떠 있어요. 진동을 감지 안 하나요?", "SIM-M14의 초록 잎은 미세 진동 감시 대기 상태다. 마지막 기록을 보려면 기록 버튼을 한 번 누른다.", "초록 잎 표시는 미세 진동 감시 대기 상태입니다. 기록 버튼으로 마지막 감지 기록을 확인할 수 있습니다."),
        "Q":("진동이 감지됐다고 계속 알리는데 민감도를 어떻게 바꾸죠?", "SIM-M14의 민감도 조절은 선반 부착 모드와 벽 부착 모드에서 다르다. 먼저 부착 위치 유형을 확인해야 한다.", "감시기를 선반에 부착하셨나요, 벽에 부착하셨나요?", "mounting_type"),
        "E":("감시기를 고정한 부분이 무너져 전원선이 찢어졌어요. 켜 볼까요?", "SIM-M14의 전원선이 찢어졌다면 기기 사용을 중단하고 전선을 직접 만지지 않으며 지원센터에 점검을 요청한다.", "기기를 켜지 말고 손상된 전선을 만지지 마세요. 지원센터에 점검을 요청해 주세요."),
        "U":("이 감시기가 책장 문을 자동으로 잠가 주나요?", "SIM-M14는 진동 기록·알림 전용이며 책장 문 잠금 기능이 없다.", "SIM-M14는 책장 문 자동 잠금 기능을 지원하지 않습니다."),
    },
    {
        "id":"F15", "product":"SIM-Q15", "name":"연습용 창가 광량 조절기", "topic":"광량·슬랫 조절",
        "A":("광량 조절기에 파란 물결 표시가 뜨는데 무슨 의미인가요?", "SIM-Q15의 파란 물결 표시는 빛 변화 추적 대기 상태다. 현재 광량을 확인하려면 보기 버튼을 누른다.", "파란 물결은 빛 변화 추적 대기 상태입니다. 보기 버튼을 눌러 광량을 확인해 주세요."),
        "Q":("햇빛이 강한데 슬랫이 안 움직여요. 어디를 봐야 하나요?", "SIM-Q15 슬랫 이동 점검은 자동 조절 모드와 고정 조절 모드에서 다르다. 먼저 현재 조절 모드를 확인해야 한다.", "슬랫 조절 모드가 자동인가요, 고정인가요?", "slat_control_mode"),
        "E":("조절기 모터 주변에서 연기와 심한 열이 납니다. 각도를 더 움직일까요?", "SIM-Q15 모터 주변에 연기·과열이 관찰되면 각도 조작을 중지하고 안전거리를 유지한 뒤 지원센터에 연락한다.", "각도 조작을 중단하고 모터에서 안전거리를 유지해 주세요. 지원센터에 연락해 주세요."),
        "U":("광량 조절기로 집 안 온도를 직접 냉방할 수 있나요?", "SIM-Q15는 광량과 슬랫만 제어하며 실내 냉방 기능은 지원하지 않는다.", "SIM-Q15는 직접 냉방 기능을 지원하지 않습니다."),
    },
    {
        "id":"F16", "product":"SIM-V16", "name":"연습용 탁상 음성 메모기", "topic":"녹음·재생",
        "A":("메모기에 분홍 책갈피 모양이 떠요. 녹음이 삭제된 건가요?", "SIM-V16의 분홍 책갈피 아이콘은 메모 북마크 저장 완료를 나타낸다. 저장 위치를 보려면 목록 버튼을 한 번 누른다.", "분홍 책갈피는 메모 북마크 저장 완료입니다. 목록 버튼으로 저장 위치를 확인할 수 있습니다."),
        "Q":("녹음 소리가 작습니다. 설정을 어디서 바꾸나요?", "SIM-V16의 녹음 음량 점검은 내장 마이크와 외부 마이크에 따라 다르다. 현재 마이크 입력 종류를 먼저 확인해야 한다.", "현재 내장 마이크를 사용하시나요, 외부 마이크를 사용하시나요?", "microphone_source"),
        "E":("메모기에서 누액과 열이 나는데 파일만 먼저 복사할까요?", "SIM-V16 배터리 누액과 과열이 함께 나타나면 파일 복사를 시도하지 말고 사용을 즉시 중단하고 지원센터에 안전 점검을 요청한다.", "파일 복사를 시도하지 말고 기기 사용을 중단해 주세요. 지원센터에 안전 점검을 요청해 주세요."),
        "U":("이 메모기가 통화 중 상대방 목소리를 전화선에서 직접 녹음하나요?", "SIM-V16은 탁상 음성 메모만 저장한다. 전화선 연결과 통화 직접 녹음 기능은 지원하지 않는다.", "SIM-V16은 전화선 연결이나 통화 직접 녹음을 지원하지 않습니다."),
    },
]

SOURCE_KINDS = ("ORIGINAL_FICTIONAL_POLICY",)
PROHIBITED_SOURCE_HINTS = ("SK매직", "SK magic", "WPUIAC", "WPUJAC", "WPU-IAC", "WPU-JAC", "WaterBridge")
ROLE_KEY = {"A":"ANSWER", "Q":"ASK", "E":"ESCALATE", "U":"EXPLAIN_UNSUPPORTED"}
PROMPT_ONLY_FIELDS = {"customer_message", "product_code", "provided_evidence", "known_conditions"}
TARGET_KEYS = {"action", "customer_message", "cited_evidence_ids", "missing_fields"}


def opaque_evidence_id(family_id: str, policy_key: str) -> str:
    """Avoid label leakage: source IDs MUST NOT encode ANSWER/ASK/E/U."""
    digest = hashlib.sha256(f"s11-source|{family_id}|policy|{policy_key}|v1".encode("utf-8")).hexdigest()[:12]
    return f"SIM-EVD-{family_id}-{digest}"


def json_dump(obj: object, indent: int | None = None) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=indent, sort_keys=False)


def make_all() -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    training, probes, probe_targets, manifest = [], [], [], []
    for i, family in enumerate(FAMILIES):
        split = "train" if i < 12 else "probe"
        f_id, product = family["id"], family["product"]
        for local_i, key in enumerate("AQEU", 1):
            q, evidence, answer, *extra = family[key]
            action = ROLE_KEY[key]
            eid = opaque_evidence_id(f_id,key)
            # Deliberately relevant-looking but inapplicable policy from SAME product.
            distractor_key = "Q" if key == "A" else "A"
            did = opaque_evidence_id(f_id,distractor_key)
            items = [
                {"id": eid, "text": evidence, "source_kind": SOURCE_KINDS[0]},
                {"id": did, "text": family[distractor_key][1], "source_kind": SOURCE_KINDS[0]},
            ]
            # Alternate position, so the correct source is not always first.
            if (i + local_i) % 2 == 0:
                items.reverse()
            prompt = {
                "customer_message": q,
                "product_code": product,
                "known_conditions": [],
                "provided_evidence": items,
            }
            target = {
                "action": action,
                "customer_message": answer,
                "cited_evidence_ids": [eid],
                "missing_fields": extra if action == "ASK" else [],
            }
            case_token = hashlib.sha256(f"s11-case|{f_id}|scenario|{key}|v1".encode("utf-8")).hexdigest()[:8]
            cid = f"S11-{f_id}-{case_token}"
            common = {
                "case_id": cid,
                "split": split,
                "semantic_group_id": f_id,
                "source_kind": SOURCE_KINDS[0],
                "review_status": "MACHINE_CHECKED_HUMAN_REVIEW_PENDING",
                "training_ready_for_waterbridge": False,
                "evaluation_origin": "CURATED_SIMULATED_EVIDENCE_NOT_BGE_RETRIEVAL",
            }
            user_message = {"role":"user", "content":json_dump(prompt)}
            if split == "train":
                training.append({**common, "messages": [
                    {"role": "system", "content": SYS_PROMPT},
                    user_message,
                    {"role": "assistant", "content": json_dump(target)},
                ]})
            else:
                probes.append({**common, "messages": [
                    {"role": "system", "content": SYS_PROMPT}, user_message,
                ], "visible_citation_ids": [x["id"] for x in items]})
                probe_targets.append({"case_id":cid, "semantic_group_id":f_id,
                    "expected_action":action, "target_FOR_EVALUATION_ONLY":target})
            manifest.append({"case_id": cid, "semantic_group_id":f_id, "split":split,
                "product_code":product, "fictional_product":family["name"],
                "topic":family["topic"], "expected_action_FOR_AUDIT_ONLY":action,
                "source_kind":SOURCE_KINDS[0], "review_status":common["review_status"]})
    return training, probes, probe_targets, manifest


def validate_all(train: list[dict], probes: list[dict], targets: list[dict], manifest: list[dict]) -> dict:
    assert len(FAMILIES) == 16 and len(train) == 48 and len(probes) == 16 and len(targets) == 16
    assert len(manifest) == 64
    assert len(set(x["case_id"] for x in manifest)) == 64
    assert len(set(x["semantic_group_id"] for x in manifest)) == 16
    assert len({x["semantic_group_id"] for x in train}) == 12
    assert len({x["semantic_group_id"] for x in probes}) == 4
    assert {x["semantic_group_id"] for x in train}.isdisjoint({x["semantic_group_id"] for x in probes})
    assert {x["case_id"] for x in probes} == {x["case_id"] for x in targets}
    train_counts = Counter(json.loads(x["messages"][-1]["content"])["action"] for x in train)
    probe_counts = Counter(x["expected_action"] for x in targets)
    assert train_counts == Counter({a:12 for a in ACTIONS})
    assert probe_counts == Counter({a:4 for a in ACTIONS})
    all_user_texts = []
    mask_checks = 0
    for x in train + probes:
        assert x["training_ready_for_waterbridge"] is False
        assert x["source_kind"] in SOURCE_KINDS
        assert re.fullmatch(r"S11-F\d\d-[0-9a-f]{8}", x["case_id"])
        messages = x["messages"]
        assert [m["role"] for m in messages] == (["system", "user", "assistant"] if x["split"] == "train" else ["system", "user"])
        prompt = json.loads(messages[1]["content"])
        assert set(prompt) == PROMPT_ONLY_FIELDS
        assert re.fullmatch(r"SIM-[A-Z]\d\d", prompt["product_code"])
        assert len(prompt["provided_evidence"]) == 2
        assert len({e["id"] for e in prompt["provided_evidence"]}) == 2
        assert len({e["text"] for e in prompt["provided_evidence"]}) == 2
        assert all(e["source_kind"] in SOURCE_KINDS for e in prompt["provided_evidence"])
        assert all(e["id"].startswith(f"SIM-EVD-{x['semantic_group_id']}-") for e in prompt["provided_evidence"])
        assert all(re.fullmatch(r"SIM-EVD-F\d\d-[0-9a-f]{12}", e["id"]) for e in prompt["provided_evidence"])
        assert "gold" not in messages[1]["content"].lower()
        assert "target" not in messages[1]["content"].lower()
        all_user_texts.append(prompt["customer_message"])
        if x["split"] == "train":
            target = json.loads(messages[2]["content"])
        else:
            target = next(v["target_FOR_EVALUATION_ONLY"] for v in targets if v["case_id"] == x["case_id"])
        assert set(target) == TARGET_KEYS
        assert target["action"] in ACTIONS and target["customer_message"]
        assert isinstance(target["cited_evidence_ids"], list) and len(target["cited_evidence_ids"]) == 1
        assert set(target["cited_evidence_ids"]).issubset({e["id"] for e in prompt["provided_evidence"]})
        assert isinstance(target["missing_fields"], list)
        assert (bool(target["missing_fields"]) == (target["action"] == "ASK"))
        relevant = next(e["text"] for e in prompt["provided_evidence"] if e["id"] == target["cited_evidence_ids"][0])
        if target["action"] == "EXPLAIN_UNSUPPORTED":
            assert "지원하지" in relevant or "기능이 없다" in relevant or "기능을 제공하지" in relevant
        if target["action"] == "ESCALATE":
            assert any(w in relevant for w in ("위험", "중단", "멈춘", "사용을 멈추", "사용을 중지", "사용하지", "조작을 중지"))
        if target["action"] == "ASK":
            assert "확인" in relevant
        full_payload = json_dump(messages)
        for bad in PROHIBITED_SOURCE_HINTS:
            assert bad not in full_payload, (x["case_id"], bad)
        mask_checks += 1
    assert len(all_user_texts) == len(set(all_user_texts))
    assert {x["semantic_group_id"] for x in manifest if x["split"] == "train"} == {f"F{i:02d}" for i in range(1,13)}
    assert {x["semantic_group_id"] for x in manifest if x["split"] == "probe"} == {f"F{i:02d}" for i in range(13,17)}
    return {"dataset_state":"FICTIONAL_DRAFT_MACHINE_VALIDATED_NOT_WATERBRIDGE_TRAINING_APPROVED",
            "scenario_cards":64, "train_rows":48, "probe_rows":16,
            "train_groups":12, "probe_groups":4,
            "train_action_counts":dict(train_counts), "probe_action_counts":dict(probe_counts),
            "all_cases_distinct_text":True, "family_disjoint":True,
            "model_input_targets_excluded_for_probes":True,
            "citation_membership_pass":mask_checks,
            "model_input_source":"ORIGINAL_FICTIONAL_CURATED_NOT_BGE_SEARCH",
            "waterbridge_s07_or_dev_holdout_used":False,
            "actual_gpu_training_performed":False,
            "manual_human_review_completed":False}


def jsonl(rows: list[dict]) -> str:
    return "".join(json_dump(row)+"\n" for row in rows)


def render_csv(rows: list[dict]) -> str:
    mem = io.StringIO(newline="")
    w = csv.DictWriter(mem, fieldnames=list(rows[0].keys()), lineterminator="\n")
    w.writeheader(); w.writerows(rows)
    return mem.getvalue()


def render_review_cards(train: list[dict], probes: list[dict], targets: list[dict]) -> str:
    target_by_id = {x["case_id"]:x["target_FOR_EVALUATION_ONLY"] for x in targets}
    out = ["# S11 — 독립 가상 시나리오 정답 검수 카드", "",
           "> **아직 사람 검수 완료 아님.** 16개 의미 그룹(제품·주제) × 4개 행동 = 64개. Train 48 / 별도 Probe 16. 실제 제품·설명서와 무관한 원본 가상 규칙이다.",
           "> **검토 핵심:** 제품/증상/조건/정답 행동/누락 정보/위험 우선순위/근거 ID/JSON 4필드. 아래 Probe 정답은 평가자 전용이므로 모델 입력에 넣지 말 것.", ""]
    for x in train + probes:
        p = json.loads(x["messages"][1]["content"])
        t = json.loads(x["messages"][2]["content"]) if x["split"] == "train" else target_by_id[x["case_id"]]
        out += [f"## {x['case_id']} — {x['split'].upper()} / {t['action']}", "",
                f"- **질문:** {p['customer_message']}",
                f"- **제품:** {p['product_code']} / 의미 그룹: {x['semantic_group_id']}",
                f"- **정답 근거:** `{t['cited_evidence_ids'][0]}`", "",
                "**모델에 제공할 가상 규칙 2개:**", ""]
        for e in p["provided_evidence"]:
            out.append(f"- `{e['id']}`: {e['text']}")
        out += ["", "**기대 답변(평가/학습 정답):**", "", "```json", json_dump(t, indent=2), "```", "",
                "- [ ] 제품 및 상황 조건이 맞음", "- [ ] 다른 규칙의 조치가 섞이지 않음", "- [ ] 인용이 실제 주장을 뒷받침함",
                "- [ ] 네 JSON 필드와 ASK 누락 필드가 올바름", "- [ ] 위험/미지원 표현이 타당함", ""]
    return "\n".join(out)+"\n"


def build_files() -> tuple[dict[str,str],dict]:
    train, probes, targets, manifest = make_all()
    summary = validate_all(train, probes, targets, manifest)
    files = {
        "s11_fictional_train_draft.jsonl": jsonl(train),
        "s11_fictional_probe_inputs.jsonl": jsonl(probes),
        "s11_fictional_probe_targets_EVAL_ONLY.jsonl":jsonl(targets),
        "s11_fictional_scenario_manifest.csv": render_csv(manifest),
        "s11_fictional_human_review_cards.md":render_review_cards(train,probes,targets),
    }
    summary["artifacts_sha256"] = {name:hashlib.sha256(content.encode("utf-8")).hexdigest() for name,content in files.items()}
    summary["group_split_manifest"] = {f["id"]:("train" if i<12 else "probe") for i,f in enumerate(FAMILIES)}
    summary["next_gate"] = "human review + tokenizer complete context length + S12 compare on untouched probe; does NOT authorize real manual training"
    files["s11_fictional_build_summary.json"] = json_dump(summary,indent=2)+"\n"
    return files, summary


def write_or_verify(path: Path, content: str) -> str:
    if path.exists():
        if path.read_bytes() != content.encode("utf-8"):
            raise FileExistsError(f"기존 다른 내용 보존: {path}")
        return "UNCHANGED"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x",encoding="utf-8",newline="\n") as fh:
        fh.write(content)
    return "WRITTEN"



def _flat_token_ids(value: object) -> list[int]:
    """Compatible with list[int] (Transformers 4) and BatchEncoding (5)."""
    data = value["input_ids"] if hasattr(value, "keys") else value
    if not isinstance(data, list) or not all(isinstance(v, int) for v in data):
        raise TypeError("Qwen tokenizer did not return a flat list of token IDs")
    return data


def run_token_check(train: list[dict], probes: list[dict], *, max_length: int = 768) -> dict:
    """Optional local CPU check. No model weights; will download tokenizer if uncached."""
    try:
        from transformers import AutoTokenizer
    except ImportError as exc:
        raise RuntimeError("--token-check에는 transformers가 필요합니다") from exc
    tok = AutoTokenizer.from_pretrained("Qwen/Qwen3-1.7B",
        revision="70d244cc86ccca08cf5af4e1e306ecf908b1ad5e",
        trust_remote_code=False)
    train_lens, assistant_lens, probe_lens = [], [], []
    for x in train:
        prompt_ids = _flat_token_ids(tok.apply_chat_template(x["messages"][:2],
            tokenize=True, add_generation_prompt=True, enable_thinking=False))
        completion_ids = tok.encode(x["messages"][2]["content"] + "<|im_end|>",
            add_special_tokens=False)
        if not prompt_ids or not completion_ids or len(prompt_ids)+len(completion_ids)>max_length:
            raise ValueError(f"Token length invalid for {x['case_id']}: "
                             f"{len(prompt_ids)} + {len(completion_ids)} > {max_length}")
        labels = [-100]*len(prompt_ids) + completion_ids
        if any(x != -100 for x in labels[:len(prompt_ids)]) or all(x == -100 for x in labels):
            raise ValueError("Completion-only loss mask invalid")
        train_lens.append(len(labels)); assistant_lens.append(len(completion_ids))
    for x in probes:
        prompt_ids = _flat_token_ids(tok.apply_chat_template(x["messages"],
            tokenize=True, add_generation_prompt=True, enable_thinking=False))
        if not prompt_ids or len(prompt_ids)>max_length:
            raise ValueError(f"Probe prompt too long: {x['case_id']}: {len(prompt_ids)} > {max_length}")
        probe_lens.append(len(prompt_ids))
    return {"train_max":max(train_lens), "train_min":min(train_lens),
            "probe_max":max(probe_lens), "assistant_token_min":min(assistant_lens),
            "masked_prompt":True, "max_length":max_length}

def run(argv: list[str] | None = None) -> int:
    ap=argparse.ArgumentParser()
    modes=ap.add_mutually_exclusive_group()
    modes.add_argument("--check",action="store_true")
    modes.add_argument("--write",action="store_true")
    modes.add_argument("--token-check",action="store_true")
    ap.add_argument("--max-length",type=int,default=768)
    args=ap.parse_args(argv)
    files, summary = build_files()
    print("[S11] FICTION CHECK PASS | 16 topic families / 64 original questions")
    print("[S11] SPLIT PASS | Train 48 (12 families) / Probe 16 (4 separate families)")
    print("[S11] ACTIONS | Train=12/12/12/12; Probe=4/4/4/4")
    print("[S11] No WaterBridge manuals, S07, real Dev/Holdout, BGE, GPU, or LLM used")
    print("[S11] HUMAN REVIEW PENDING | Fictional draft only; not real customer-service SFT approval")
    if args.token_check:
        train, probes, _, _ = make_all()
        lengths=run_token_check(train,probes,max_length=args.max_length)
        print("[S11] TOKEN CHECK PASS | " + json_dump(lengths))
    if args.write:
        names=[]
        for name, content in files.items():
            path = OUT/name
            state = write_or_verify(path,content)
            names.append((name,state))
        print("[S11] WRITE PASS | " + ", ".join(n for n,_ in names))
    else:
        print("[S11] CHECK PASS (read-only; --write creates output files)")
    return 0

if __name__ == "__main__":
    try: raise SystemExit(run())
    except (ValueError,FileExistsError,AssertionError,KeyError,TypeError,RuntimeError,ImportError) as e:
        print(f"[S11] ERROR: {type(e).__name__}: {e}",file=sys.stderr);raise SystemExit(1)
