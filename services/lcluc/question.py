"""Parse bounded Korean, Indonesian and English land-cover questions."""

from dataclasses import dataclass
from re import IGNORECASE, compile, findall
from unicodedata import normalize

DOC = compile(r"\batbd\b|glossary|fact sheet|legend|definition|method|policy|what is|gap fill|spatial filter|temporal filter|accuracy assessment|definisi|metod|apa itu|kebijakan|legenda|용어|범례|정의|방법|설명|정책|참조 지도")
AMOUNT = compile(r"\b(?:berapa|how much|how many|hectares?|hektare|ha)\b|얼마|몇\s*(?:ha|헥타르|제곱)|수치|계산")
AREA = compile(r"\b(?:areas?|extent|luas|luasan|hectares?|hektare)\b|면적|넓이")
LOSS = compile(r"deforest|forest[- ]loss|loss of forest|forest decline|kehilangan hutan|penurunan (?:luas )?hutan|산림\s*(?:순\s*)?(?:감소|손실|훼손)")
NET = compile(r"\bnet\b|bersih|순감소|순변화|순손실")
TRANSITION = compile(r"transition|transisi|konversi|beralih|menjadi|perubahan|changed? (?:from|to)|전이|전환|변화량|→|->")
OVERLAP = compile(r"overlap|intersect|overlay|tumpang tindih|irisan|중첩|교차")
RATE = compile(r"%|percent|persen|감소율|전이율|\brates?\b|\blaju\b")
OTHER_UNIT = compile(r"\b(?:acres?|km\s*[²2]|m\s*[²2]|square kilometers?)\b|제곱킬로미터|제곱미터")
COLLECTION = compile(r"(?:collection|koleksi|컬렉션|버전)\s*(\d(?:\.\d+)?)\b|\bv(\d\.\d+)\b")
ESRI_VERSION = compile(r"\bv(\d{3})\b")
DIRECTION = compile(r"(?:[- ]to[- ]|→|->|에서|에서부터|\bke\b|\bmenjadi\b|\binto\b)")
OTHER_LOCATION = compile(r"jawa\s+(?:barat|timur|tengah)|west java|east java|central java|jakarta|serang|tangerang|cilegon|pandeglang|lebak|sumatra|sulawesi|kalimantan|자카르타|자바|수마트라|술라웨시|칼리만탄|세랑|탕에랑|\b(?:district|kabupaten|village|bbox)\b|군·시|구역별")
REGION = compile(r"\bbanten\b|반텐|반튼")
PRODUCTS = {
    "mapbiomas": compile(r"map\s*biomas|맵바이오마스|landy"),
    "esri": compile(r"\besri\b|impact observatory|에스리"),
    "kemenhut": compile(r"kemenhut|\bklhk\b|kehutanan|sigap|penutupan lahan resmi|indonesian (?:forestry ministry|ministry of forestry)|산림부|환경산림부|환경청"),
    "sentinel-2": compile(r"sentinel[ -]?2|센티넬"),
    "landsat": compile(r"landsat|랜드샛"),
    "worldcover": compile(r"world\s*cover|월드커버"),
}

CLASS_TERMS = compile(
    r"(?P<forest_formation>\bforest formation\b|\bformasi hutan\b|산림형성지)"
    r"|(?P<mangrove>\bmangroves?\b|맹그로브)"
    r"|(?P<peat_forest>\bpeat swamp forest\b|\bhutan rawa gambut\b|이탄습지림)"
    r"|(?P<other_agriculture>\bother agriculture\b|\bpertanian lainnya\b|기타 농경지)"
    r"|(?P<rice>\bsawah\b|\brice(?:\s+padd(?:y|ies))?\b|논)"
    r"|(?P<palm>\boil palm\b|\bkelapa sawit\b|\bsawit\b|팜유)"
    r"|(?P<agriculture>\bagriculture\b|\bpertanian\b|농업)"
    r"|(?P<crops>\bcroplands?\b|\bcrops?\b|농경지)"
    r"|(?P<urban>\burban\b|\bbuilt[- ]up\b|\bpermukiman\b|시가지|시가화)"
    r"|(?P<natural_nonforest>\bnon[- ]forest natural vegetation\b|비산림 자연식생)"
    r"|(?P<nonforest>\bnon[- ]?forests?\b|\bnon[- ]?hutan\b|비산림|비산림지)"
    r"|(?P<forest>\bforests?\b|\bhutan\b|산림)"
    r"|(?P<trees>\btrees?\b|\bpohon\b|수목)"
    r"|(?P<aquaculture>\baquaculture\b|\btambak\b|양식장)"
    r"|(?P<water>\bwater(?: body)?\b|\bperairan\b|수역)"
    r"|(?P<flooded>\bflooded vegetation\b|침수 식생)"
    r"|(?P<nonvegetation>\bother non[- ]vegetation\b|기타 비식생)"
    r"|(?P<bare>\bbare ground\b|나지)"
    r"|(?P<rangeland>\brangeland\b|초지·관목지)",
    IGNORECASE,
)
ALL_CLASSES = compile(r"\ball (?:classes|land cover types)\b|\bsemua kelas\b|클래스별|전체\s*(?:클래스|분류)|토지피복별")


@dataclass(frozen=True)
class Intent:
    metric: str
    region: str | None = None
    product: str | None = None
    years: tuple[int, ...] = ()
    classes: tuple[str, ...] = ()
    document: bool = False
    issue: str | None = None


def parse_question(question):
    text = normalize("NFKC", question).casefold()
    years = tuple(dict.fromkeys(map(int, findall(r"(?<!\d)(?:19|20)\d{2}(?!\d)", text))))
    products = [name for name, pattern in PRODUCTS.items() if pattern.search(text)]
    product = products[0] if len(products) == 1 else None
    region = "banten" if REGION.search(text) else None
    matches = list(CLASS_TERMS.finditer(text))
    classes = tuple(dict.fromkeys(match.lastgroup for match in matches))
    directed = len(matches) == 2 and bool(DIRECTION.search(text[matches[0].end():matches[1].start()]))
    overlap, loss, transition, area = (pattern.search(text) for pattern in (OVERLAP, LOSS, TRANSITION, AREA))
    document = bool(DOC.search(text))
    amount = bool(AMOUNT.search(text))
    if document and not (amount or (years and (overlap or loss or transition or area))):
        return Intent("document", document=True)
    if overlap:
        metric = "overlap"
    elif (loss or (NET.search(text) and "forest" in classes and (area or transition))) and not directed:
        metric = "forest_net_change" if NET.search(text) else "forest_loss"
        classes = ("forest",)
    elif directed or transition:
        metric = "transition"
    elif area or amount:
        metric = "area"
    else:
        return Intent("unknown", issue="INTENT_REQUIRED")

    issue = None
    if OTHER_LOCATION.search(text):
        issue = "BANTEN_PROVINCE_ONLY"
    elif len(products) > 1:
        issue = "PRODUCT_AMBIGUOUS"
    elif product == "mapbiomas" and any((version or tag) != "4.1" for version, tag in COLLECTION.findall(text)):
        issue = "PRODUCT_VERSION_NOT_READY"
    elif product == "esri" and any(version != "003" for version in ESRI_VERSION.findall(text)):
        issue = "PRODUCT_VERSION_NOT_READY"
    elif RATE.search(text) or OTHER_UNIT.search(text):
        issue = "AREA_UNIT_REQUIRED"
    elif metric != "overlap" and product not in (None, "kemenhut", "sentinel-2", "landsat", "worldcover"):
        expected_years = 1 if metric == "area" else 2
        if len(years) != expected_years or tuple(sorted(years)) != years:
            issue = "AREA_YEAR_REQUIRED" if expected_years == 1 else "ORDERED_YEAR_PAIR_REQUIRED"
        elif metric == "transition" and not directed:
            issue = "TRANSITION_DIRECTION_REQUIRED"
        elif metric == "area" and not classes and ALL_CLASSES.search(text):
            classes = ("all",)
        elif metric == "area" and len(classes) != 1:
            issue = "AREA_CLASS_REQUIRED"
    return Intent(metric, region, product, years, classes, document=document, issue=issue)
