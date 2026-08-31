"""Generated questions may collect facts, never introduce repair tasks."""

from __future__ import annotations

import re
import unicodedata

from ..safety.rule_loader import SafetyRuleLoader


class FollowUpWordingGuard:
    _REPAIR = re.compile(
        r"분해|직접수리|배선작업|전기작업|피복|기판|수리|"
        r"(?:전선|배선|전기선|전원선|내부케이블).{0,12}(?:자르|연결|교체|만지|접촉|확인|점검|살펴|살핀|보|봐|훑)|"
        r"나사.{0,12}(?:풀|조)|내부.{0,12}(?:확인|점검|열|뜯|살펴|살핀|보|봐|훑)|"
        r"(?:커버|덮개|외장|패널|뒷판|앞판|뒷면|케이스).{0,12}(?:열|뜯|벗|제거|분리|탈거|떼|빼)|"
        r"(?:부품|밸브|모터).{0,12}(?:갈아|교체|조여|뜯)"
    )
    _DIAGNOSIS = re.compile(r"(?:원인|고장|불량|결함|파손|누전).{0,12}(?:확정|확실|분명|100%|입니다|이에요|이다|이므로|이니|때문)")
    _SAFETY = re.compile(
        r"안전(?:합니다|해요|하니|하므로|함)|(?:안전한|무해한)(?:물|제품)|안전을보증|절대안전|100%안전|"
        r"(?:마셔도|음용해도|사용해도).{0,12}(?:안전|괜찮|됩|돼|무방)|음용가능|"
        r"안심하고.{0,12}(?:마셔|사용)|(?:수질|인체|유해물질).{0,12}(?:문제.{0,3}없|무해|전혀없|안전)"
    )
    _NEW_ACTION = re.compile(
        r"(?:분해|수리|연결|교체|확인|점검|재부팅|청소|조작|음용|시도)(?:을|를)?(?:직접|다시)?(?:해|하)"
        r"(?:주시|주세|보시|보세|보실|볼|시고|신후|신뒤|셔야|도록|야|면)|"
        r"(?:열어|뜯어|풀어|조여|만져|잘라|눌러|뽑아|꺼|켜|마셔)(?:보시|보세|보실|볼|주세|주시|서|야)|"
        r"(?:분해|수리|연결|교체|점검|재부팅|청소)(?:한|하신)(?:후|뒤)"
    )
    _HISTORY = re.compile(r"(?:했|하셨|해봤|해보셨|보셨)(?:나요|습니까)\?$|(?:한|하신|해본|해보신|본)(?:적|경험|내용)(?:이|은|가)?(?:있나요|있으신가요)\?$")
    _FUTURE = re.compile(r"겠|볼까|할까|보실|보시|주세요|주시|하면|해야|해도|하시고|해보고|한후|한뒤|해서|하여|필요|권장|추천|하나요|가능|합시다")

    @staticmethod
    def _compact(text):
        return "".join(c for c in unicodedata.normalize("NFKC", text)
                       if not c.isspace() and unicodedata.category(c) != "Cf")

    def validate(self, text: str, *, target_field: str, is_question: bool) -> None:
        text = self._compact(text)
        policy = SafetyRuleLoader().get_prohibited_expressions()
        for name in ("prohibited_diagnosis_phrases", "prohibited_guarantee_phrases", "prohibited_repair_action_phrases"):
            if any(self._compact(phrase) in text for phrase in policy.get(name, ())):
                raise ValueError("후속 질문의 금지 표현")
        if self._DIAGNOSIS.search(text) or self._SAFETY.search(text) or self._NEW_ACTION.search(text):
            raise ValueError("후속 질문은 진단·보증·새 조치를 지시할 수 없습니다.")
        if is_question and text.count("?") != 1:
            raise ValueError("후속 질문은 하나의 질문이어야 합니다.")
        if self._REPAIR.search(text) and not (
            is_question and target_field == "actions_taken"
            and self._HISTORY.search(text) and not self._FUTURE.search(text)
        ):
            raise ValueError("후속 질문은 직접 수리를 유도할 수 없습니다.")


__all__ = ["FollowUpWordingGuard"]
