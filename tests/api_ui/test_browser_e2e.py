"""명시적으로 켠 로컬 Playwright 검증만 허용. 기본 브라우저 검증은 Root 담당이다."""

import os
from urllib.parse import urlsplit

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("SDSS_BROWSER_E2E") != "1",
    reason="Root computer-use 또는 명시적 SDSS_BROWSER_E2E=1 필요",
)


@pytest.fixture
def page():
    sync = pytest.importorskip("playwright.sync_api")
    base = os.getenv("SDSS_UI_BASE", "http://127.0.0.1:8010")
    if urlsplit(base).hostname not in ("127.0.0.1", "localhost"):
        pytest.fail("로컬 검증 URL만 허용")
    with sync.sync_playwright() as runtime:
        try:
            browser = runtime.chromium.launch(headless=True)
        except Exception as error:
            pytest.skip("Playwright Chromium 미설치: " + type(error).__name__)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(base, wait_until="domcontentloaded")
        yield page
        browser.close()


def test_health_cckp_reproduction_and_disabled_execution(page):
    page.get_by_test_id("health-check").click()
    page.get_by_test_id("health-output").filter(has_text="VERIFIED_REAL").wait_for()
    page.get_by_test_id("cckp-load").click()
    page.wait_for_function(
        "document.querySelector('[data-testid=cckp-value]').textContent!=='미조회'"
    )
    assert page.get_by_test_id("training-execute").is_disabled()
    assert page.get_by_test_id("deployment-execute").is_disabled()
    page.get_by_test_id("climate-contract").click()
    page.wait_for_function(
        "document.querySelector('[data-testid=climate-request]').value.includes('geography')"
    )
    page.get_by_test_id("climate-run").click()
    page.get_by_test_id("climate-output").filter(
        has_text="LOCAL_PINNED_GRID_REPRODUCTION"
    ).wait_for()


def test_numeric_rag_and_private_report_search_stay_blocked(page):
    page.get_by_test_id("rag-question").fill("2050년 강수량은 얼마인가?")
    page.get_by_test_id("rag-search").click()
    page.get_by_test_id("rag-output").filter(has_text="NUMERIC_TOOL_REQUIRED").wait_for()
    page.get_by_test_id("rag-question").fill("CCKP methodology")
    page.get_by_test_id("report-search").click()
    page.get_by_test_id("report-output").filter(has_text="BLOCKED").wait_for()
    page.get_by_test_id("vector-status").click()
    page.get_by_test_id("vector-output").filter(has_text="public_search_enabled").wait_for()


def test_mobile_sections_and_input_error(page):
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.get_by_test_id("health-check").is_visible()
    page.get_by_test_id("climate-request").fill("{broken")
    page.get_by_test_id("climate-run").click()
    page.get_by_test_id("climate-output").filter(has_text="INVALID_JSON_OR_API_FAILURE").wait_for()
