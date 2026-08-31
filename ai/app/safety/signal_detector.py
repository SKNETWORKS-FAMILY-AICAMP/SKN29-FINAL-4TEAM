"""Detect explicit physical observations independently of Provider availability."""

from __future__ import annotations

import re
import unicodedata

_PART = r"(?:전선|전원선|전원\s*코드|케이블|플러그|콘센트)"
_DAMAGE = r"(?:벗겨|손상|찢어|끊어|파손)"
_WATER = r"물(?:이|가|은|도)?(?=$|\s|[.!?])"
_PATTERNS = {
    "electrical_component_damage": re.compile(rf"{_PART}.{{0,16}}?{_DAMAGE}|{_DAMAGE}.{{0,12}}?{_PART}"),
    "exposed_wire": re.compile(rf"(?:구리선|도체).{{0,8}}?(?:노출|보이|드러)|{_PART}.{{0,12}}?(?:피복.{{0,6}}?벗겨|노출|속이\s*보)"),
    "water_near_electrical_part": re.compile(
        rf"{_PART}.{{0,16}}?(?:젖|물기|누수|침수|물(?:이|가|에)?\s*(?:고|새|묻|튀|흐르|들어(?:가|갔|오|왔)|잠(?:기|겨|겼)))"
        rf"|(?:물기|누수|젖).{{0,12}}?{_PART}|{_PART}\s*(?:주변|근처|옆|아래)에?\s*{_WATER}"
    ),
    "water_leak": re.compile(
        r"누수|(?:물|냉수|온수|정수)(?:이|가|는|도)?\s*(?:자꾸|계속)?\s*"
        r"(?:새(?:요|네요|어|고|는|지|면|서|다)|샙|샘(?=$|\s|[.!?])|샜|흘러나)"
        rf"|(?:바닥|제품\s*(?:밑|아래|하부)|정수기\s*(?:밑|아래|하부)).{{0,8}}?(?:{_WATER}|젖)"
    ),
    "smoke_or_burn": re.compile(r"연기|화재|불이\s*남|탄\s*냄새|타는\s*냄새|그을"),
    "shock_or_spark": re.compile(r"감전|스파크|불꽃|찌릿"),
}
_BOUNDARY = re.compile(
    r"[.!?\n;,]|하지만|그런데|다만|(?:없|아니|않)[가-힣]{0,3}(?:고|지만)"
    r"|(?<=[가-힣])(?:지만|는데|은데|인데)(?:도)?(?=\s|$|[,.!?])"
    r"|(?<=[가-힣])고(?=\s+(?!있|없|싶|보이)[가-힣]{2,}(?:에는|은|는|이|가|도)\s)"
)
_DENIAL = re.compile(
    r"없|아니(?:에요|예요|어요|고|라|며|다|요|지만|죠)|아닙|아님"
    r"|(?:나|발생하|튀|새|새어|벗겨지|노출되|손상되|파손되|젖|보이|들어가|들어오|잠기|침수되)지\s*않"
    r"|안\s*(?:나|발생|튀|새|벗겨|노출|손상|젖|보|들어|잠|침수)"
)
_HYPOTHETICAL = re.compile(
    r"라면|다면|일\s*경우|가정|(?:나|발생하|튀|새|벗겨지|노출되|손상되|들어가|들어오|잠기|침수되)면|젖으면"
)
_MENTION = re.compile(rf"{_PART}|연기|화재|스파크|불꽃|누수|감전|히터|온수\s*모듈|물(?:이|가|은|도)?")
_BUTTON_ALERT = re.compile(
    r"(?P<controls>(?:온수|정수|냉수)[^.!?\n]{0,48}?)(?:버튼|선택\s*표시등)"
    r"(?:들)?(?:이|은|는|도|가)?\s*"
    r"(?:(?:전부|모두|다|동시에|함께|일제히)\s*)+"
    r"(?:깜박(?:이|거리)?|깜빡(?:이|거리)?|점멸(?:하)?)"
)
_RED_DISPLAY = re.compile(
    r"(?:표시창|디스플레이|화면|led|lcd)(?:이|가|은|는|도|에)?\s*"
    r"(?:빨간\s*(?:색|불)|빨갛|빨강|붉은\s*(?:색|불)|붉|적색)"
)
_INDICATOR_CONDITION = re.compile(
    r"지\s*않|아닌|(?:깜박|깜빡|점멸|켜|들어오|변)[가-힣]{0,8}면|경우|일\s*때"
    r"|안\s*(?:깜박|깜빡|점멸|켜|들어오|변)|(?:색|빨강)(?:이|이라)?면"
)


def _normalize(text: str) -> str:
    return "".join(char for char in unicodedata.normalize("NFKC", text).casefold()
                   if unicodedata.category(char) != "Cf")


def _asserted(text: str, start: int, end: int, *, negated_predicate: bool = False) -> bool:
    left, right = 0, len(text)
    for boundary in _BOUNDARY.finditer(text):
        if boundary.end() <= start:
            left = boundary.end()
        elif boundary.start() >= start and boundary.end() >= end:
            # A predicate match may include the first syllable of "새지만".
            # Keep that connector inside its clause, but exclude the next one.
            right = boundary.end()
            break
    for mention in _MENTION.finditer(text, end, right):
        if text[end:mention.start()].strip() not in {"와", "과", "및", "하고", "랑", "이랑", "도", ","}:
            right = mention.start()
            break
    # For a condition such as "온수가 안 나", the negative predicate names
    # the observation itself. Only a following denial may negate that condition.
    after = text[end if negated_predicate else start:min(right, end + 28)]
    if re.fullmatch(r"(?:순간\s*)?온수\s*모듈|(?:온수\s*)?히터", text[start:end]) and re.match(
        r"(?:은|는|이|가|도)?\s*정상(?:입니다|이에요|이다|임|이고|인데|이지만)", text[end:right]
    ):
        return False
    if "만약" in text[max(left, start - 8):start] or _HYPOTHETICAL.search(after):
        return False
    if not re.search(r"없지\s*않|없는\s*것은\s*아니", after):
        if _DENIAL.search(after.replace("뿐 아니라", "")):
            return False
    return True


def has_asserted_keyword(text: str, keyword: str, *, negated_predicate: bool = False) -> bool:
    normalized = _normalize(text)
    return any(_asserted(normalized, m.start(), m.end(), negated_predicate=negated_predicate)
               for m in re.finditer(re.escape(_normalize(keyword)), normalized))


def detect_safety_evidence(text: str) -> tuple[tuple[str, str], ...]:
    normalized = _normalize(text)
    result = []
    for name, pattern in _PATTERNS.items():
        for match in pattern.finditer(normalized):
            if _asserted(normalized, match.start(), match.end()):
                result.append((name, match.group(0)))
                break
    return tuple(result)


def has_asserted_hot_water_panel_alert(text: str) -> bool:
    """Recognize the combined heater alert described in IAC425 p46 / IAC606 p43.

    This is an observation detector, not an evaluation-case lookup. All three
    water controls must blink together and the display must be red; an ordinary
    lock light, one blinking control, a denial or a hypothetical is insufficient.
    The caller maps it to the existing approved heater rule and its guidance.
    """
    normalized = _normalize(text)

    def asserted_indicator(match: re.Match[str]) -> bool:
        right = next(
            (boundary.start() for boundary in _BOUNDARY.finditer(normalized, match.end())),
            len(normalized),
        )
        clause = normalized[match.start():min(right, match.end() + 28)]
        return (
            _asserted(normalized, match.start(), match.end())
            and not _INDICATOR_CONDITION.search(clause)
        )

    displays = [match for match in _RED_DISPLAY.finditer(normalized) if asserted_indicator(match)]
    for buttons in _BUTTON_ALERT.finditer(normalized):
        controls = buttons.group("controls")
        if set(re.findall(r"온수|정수|냉수", controls)) != {"온수", "정수", "냉수"}:
            continue
        # Only a list of controls is accepted: exclude "냉수만", "온수 제외", etc.
        if re.sub(r"온수|정수|냉수|이랑|하고|와|과|및|랑|[\s\[\],·/&]", "", controls):
            continue
        if asserted_indicator(buttons) and any(
            abs(display.start() - buttons.end()) <= 160 for display in displays
        ):
            return True
    return False


def supports_safety_quote(text: str, signal_name: str, quote: str) -> bool:
    pattern = _PATTERNS.get(signal_name)
    normalized, quote = _normalize(text), _normalize(quote)
    if pattern is None or not quote.strip():
        return False
    return any(
        _asserted(normalized, source.start() + match.start(), source.start() + match.end())
        for source in re.finditer(re.escape(quote), normalized)
        for match in pattern.finditer(quote)
    )


__all__ = [
    "detect_safety_evidence", "has_asserted_keyword", "supports_safety_quote",
    "has_asserted_hot_water_panel_alert",
]
