import pytest

from services.api import lcluc_geollm
from services.lcluc.question import parse_question


@pytest.mark.parametrize(("question", "kind", "classes"), [
    ("MapBiomas ATBD의 Gap Fill 방법은?", "document", ()),
    ("Berapa luas sawah di Banten pada 2024 menurut MapBiomas?", "area", ("rice",)),
    ("Show MapBiomas forest-to-urban transitions in Banten from 2023 to 2024", "transition", ("forest", "urban")),
    ("MapBiomas 반텐 2023년부터 2024년까지 산림 감소량은?", "forest_loss", ("forest",)),
    ("MapBiomas 반텐 2023년부터 2024년까지 산림 순감소는?", "forest_net_change", ("forest",)),
])
def test_multilingual_intent(question, kind, classes):
    result = parse_question(question)
    assert result.metric == kind and result.classes == classes and result.issue is None


def test_blocked_query_does_not_invoke_document_retrieval_as_fallback(monkeypatch):
    def never(*args):
        pytest.fail("Numeric-only query invoked document retrieval")

    def unavailable(*args):
        raise FileNotFoundError

    monkeypatch.setattr(lcluc_geollm, "document_search", never)
    monkeypatch.setattr(lcluc_geollm, "mapbiomas_answer", unavailable)
    questions = {
        "반텐 산림부 2023년부터 2024년까지 산림 감소량은?": "KEMENHUT_ASSET_NOT_READY",
        "MapBiomas Esri Banten rice area 2024": "PRODUCT_AMBIGUOUS",
        "MapBiomas Banten and West Java rice area 2024": "BANTEN_PROVINCE_ONLY",
        "MapBiomas Banten rice area 2024": "EVIDENCE_NOT_READY",
        "MapBiomas Collection 3.0 Banten rice area 2024": "PRODUCT_VERSION_NOT_READY",
        "Esri v002 Banten tree area 2024": "PRODUCT_VERSION_NOT_READY",
        "MapBiomas Banten 2023 to 2024 forest and urban transitions": "TRANSITION_DIRECTION_REQUIRED",
    }
    for question, reason in questions.items():
        reply = lcluc_geollm.answer_question(None, question)
        assert reply["status"] == "BLOCKED" and reply["route"] == "gis" and reply["reason"] == reason
        assert reply["metrics"] == reply["citations"] == []


def test_forest_loss_uses_transition_margins_and_net_change_uses_annual_areas():
    cover = {"years": [2023, 2024], "classes": [
        {"code": 3, "name": "Forest", "areas_ha": [100, 95]},
        {"code": 24, "name": "Urban", "areas_ha": [10, 15]},
    ]}
    table = {"periods": ["2023-2024"], "pairs": {
        "3:3": {"areas_ha": [90], "row": 1}, "3:24": {"areas_ha": [10], "row": 2},
        "24:3": {"areas_ha": [5], "row": 3}, "24:24": {"areas_ha": [5], "row": 4},
    }}
    intent = parse_question("MapBiomas Banten forest loss from 2023 to 2024")
    values, _, sheet, limitations, rows = lcluc_geollm.mapbiomas_values(intent, cover, table)
    assert sheet == "TRANSITION" and values[0]["value"] == 10 and rows == [2]
    assert "FOREST_START_MARGIN_CHECKED" in limitations
    net = parse_question("MapBiomas Banten net forest area change from 2023 to 2024")
    values, _, sheet, _, _ = lcluc_geollm.mapbiomas_values(net, cover)
    assert sheet == "COVERAGE" and values[0]["value"] == -5
    table["pairs"]["3:3"]["areas_ha"][0] = 89
    with pytest.raises(lcluc_geollm.Unavailable, match="COVERAGE_MISMATCH"):
        lcluc_geollm.mapbiomas_values(intent, cover, table)


def test_no_missing_transition_value_or_period_is_replaced_by_zero():
    table = {"periods": ["2023-2024"], "pairs": {"3:24": {"areas_ha": [None], "row": 19}}}
    with pytest.raises(lcluc_geollm.Unavailable, match="TRANSITION_NOT_PUBLISHED"):
        lcluc_geollm.sum_transitions(table, "2023-2024", {3}, {24})
    with pytest.raises(lcluc_geollm.Unavailable, match="PERIOD_NOT_PUBLISHED"):
        lcluc_geollm.sum_transitions(table, "2022-2024", {3}, {24})
