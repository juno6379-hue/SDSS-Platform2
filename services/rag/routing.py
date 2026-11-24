"""다국어 변수 이름 정규화 및 정량 질문의 구조화 도구 전용 라우팅."""

import re
from dataclasses import dataclass

VARIABLE_ALIASES = {
    "tas": (
        "tas",
        "기온",
        "평균 기온",
        "temperature",
        "mean temperature",
        "suhu",
        "suhu rata-rata",
    ),
    "pr": ("pr", "강수량", "강수", "precipitation", "rainfall", "curah hujan", "presipitasi"),
    "tasmax": ("tasmax", "최고 기온", "maximum temperature", "suhu maksimum"),
    "tasmin": ("tasmin", "최저 기온", "minimum temperature", "suhu minimum"),
    "sfcWind": ("sfcwind", "풍속", "wind speed", "kecepatan angin"),
    "hurs": ("hurs", "상대 습도", "relative humidity", "kelembapan relatif"),
}
_ALIASES = sorted(
    ((alias, canonical) for canonical, aliases in VARIABLE_ALIASES.items() for alias in aliases),
    key=lambda x: (-len(x[0]), x[0]),
)


def canonical_tokens(text):
    value = text.casefold()
    # 긴 alias부터 치환해 maximum temperature를 평균 기온으로 잘못 합치지 않는다.
    for alias, canonical in _ALIASES:
        pattern = re.escape(alias)
        if alias.isascii():
            pattern = r"(?<!\w)" + pattern + r"(?!\w)"
        value = re.sub(pattern, canonical.casefold(), value)
    return tuple(re.findall(r"[\w]+", value, flags=re.UNICODE))


def variables_in(text):
    tokens = set(canonical_tokens(text))
    return tuple(sorted(key for key in VARIABLE_ALIASES if key.casefold() in tokens))


@dataclass(frozen=True)
class RouteDecision:
    kind: str
    tool_id: str | None
    status: str
    variables: tuple[str, ...]
    missing_fields: tuple[str, ...]
    reason: str


REQUIRED_NUMERIC_CONTEXT = (
    "variable",
    "unit",
    "observed_or_projected",
    "model",
    "scenario",
    "time_period",
    "geography",
    "calendar",
    "grid",
    "aggregation",
)


def route_question(question, context=None):
    if not isinstance(question, str) or not question.strip() or len(question) > 4000:
        raise ValueError("질문은 1~4000자")
    context = context or {}
    value = question.casefold()
    variables = variables_in(question)
    quantitative = bool(
        re.search(
            r"얼마|몇|수치|평균|합계|추세|비교|증가율|감소율|백분율|값|확률|현재|오늘|알려|보여|berapa|nilai|rata.rata|jumlah|persen|tren|selisih|sekarang|hari ini|how much|how many|average|total|trend|percent|difference|value|probability|\bcurrent\b|\bnow\b|(?<!\d)(?:18|19|20|21|22)\d{2}(?!\d)|\d\s*(?:°|mm|%|degrees)",
            value,
        )
    )
    # 숫자를 문자로 쓴 질문도 놓치지 않도록, 변수 질의는 설명 의도가 명확하지 않으면 도구로 보낸다.
    descriptive = bool(
        re.search(
            r"methodology|definition|meaning|metadata|방법|정의|의미|개념|설명|metodologi|definisi|pengertian",
            value,
        )
    )
    quantitative = quantitative or bool(variables and not descriptive)
    # 수치 의도가 있으면 변수 식별이 실패해도 RAG로 되돌리지 않는다.
    if quantitative:
        supplied = dict(context)
        if len(variables) == 1:
            supplied.setdefault("variable", variables[0])
        missing = tuple(
            field
            for field in REQUIRED_NUMERIC_CONTEXT
            if supplied.get(field) is None or supplied.get(field) == ""
        )
        return RouteDecision(
            "structured_climate_tool",
            "climate.query",
            "BLOCKED" if missing else "TOOL_REQUIRED",
            variables,
            missing,
            "기후 수치는 공식 API/Grid/Parquet/PostGIS 도구에서만 조회; RAG 수치 답변 금지",
        )
    return RouteDecision(
        "descriptive_rag",
        None,
        "RETRIEVAL_ONLY",
        variables,
        (),
        "설명용 인용 검색; 수치 사실 생성 없음",
    )
