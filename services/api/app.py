"""Loopback evidence API, catalog, and authority-gated execution interfaces."""

import asyncio
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.concurrency import run_in_threadpool

from services.climate_query.models import ClimateQueryRequest, tool_contract
from services.climate_query.numeric import climate_query
from services.datahub.institution_sources import build_inventory, public_summary
from services.lcluc.question import parse_question
from services.mlops.gates import MLOpsPolicy
from services.orchestration import WorkflowState
from services.rag.retrieval import SearchQuery
from services.rag.routing import route_question

from .collection_progress import snapshot as collection_snapshot
from .evidence import LOCK_PATH, ROOT, EvidenceBlocked, EvidenceStore
from .geollm_storage import DataLakeGeoLLMStorage, StorageBlocked, select_geollm_storage
from .jobs_api import mount_jobs
from .lcluc_annual import mount_lcluc_annual
from .lcluc_cases import mount_lcluc_cases
from .lcluc_geollm import mount_lcluc_geollm, search_documents
from .lcluc_landsat_explorer import mount_landsat_explorer
from .lcluc_postprocess import mount_postprocess
from .lcluc_sentinel_explorer import mount_sentinel_explorer
from .model_releases import mount_model_releases
from .operation_lineage import mount_operation_lineage
from .pinned import LOCK_SHA256
from .results import check_local, mount_results, registration_snapshot

CCKP = "evidence/cckp_indonesia/"
KLHK = "evidence/klhk_rag/"
SENTINEL = "evidence/onemap_sentinel/"


class RagRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=2000)
    scope: Literal["mapbiomas-indonesia"] | None = None


def blocked(code, **extra):
    return dict(status="BLOCKED", blockers=[code], value=None, execution_started=False, **extra)


def create_app(store=None, curated_index=None, *, result_registry=None, geollm_lake=None):
    store = store or EvidenceStore(ROOT, LOCK_PATH, LOCK_SHA256)
    geollm_storage = select_geollm_storage(store, geollm_lake)

    @asynccontextmanager
    async def lifespan(app):
        warmup = None
        if isinstance(geollm_storage, DataLakeGeoLLMStorage) and not geollm_storage.config_issue and geollm_lake is None:
            geollm_storage.warming_documents.set()
            warmup = asyncio.create_task(run_in_threadpool(geollm_storage.warm_documents))
        try:
            yield
        finally:
            if warmup is not None and not warmup.done():
                warmup.cancel()

    app = FastAPI(title="SDSS Platform2 · Evidence API", version="0.1.0", lifespan=lifespan)
    app.state.store = store

    @app.middleware("http")
    async def protect(request: Request, call_next):
        if (
            request.headers.get("content-length", "").isdigit()
            and int(request.headers["content-length"]) > 65536
        ):
            return JSONResponse(blocked("REQUEST_BODY_TOO_LARGE"), status_code=413)
        origin = request.headers.get("origin")
        if origin and origin != str(request.base_url).rstrip("/"):
            return JSONResponse(blocked("CROSS_ORIGIN_REQUEST_DENIED"), status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
        )
        return response

    @app.exception_handler(EvidenceBlocked)
    async def evidence_error(request, error):
        return JSONResponse(blocked(str(error)), status_code=409)

    mount_results(app, store, result_registry)
    mount_model_releases(app, store, result_registry)
    mount_jobs(app, store, result_registry)
    mount_lcluc_cases(app, store, result_registry)
    mount_lcluc_geollm(app, geollm_storage)
    mount_sentinel_explorer(app, store)
    mount_landsat_explorer(app, store)
    mount_postprocess(app, store)
    mount_lcluc_annual(app, store)
    mount_operation_lineage(app)

    @app.get("/api/institution-sources")
    def institution_sources(request: Request):
        check_local(request)
        return public_summary(build_inventory(store.root))

    @app.get("/api/health")
    def health():
        return {
            "status": "VERIFIED_REAL",
            "scope": "LOCAL_API_PROCESS_ONLY",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "provider_health_checked": False,
            "training_executed": False,
            "deployment_executed": False,
        }

    @app.get("/api/cckp")
    def cckp():
        result, proof = store.read_json("cckp", CCKP + "numeric-result-validated.json")
        if result.get("status") != "VERIFIED_REAL":
            raise EvidenceBlocked("NUMERIC_RESULT_NOT_VERIFIED")
        raw_pin = store._lock()["groups"]["cckp"]["files"][CCKP + "global-asset.nc"]["sha256"]
        if result.get("provenance", {}).get("raw_sha256") != raw_pin:
            raise EvidenceBlocked("RESULT_RAW_LINEAGE_MISMATCH")
        return {
            "status": "VERIFIED_REAL",
            "evidence": proof,
            "result": result,
            "mode": "PINNED_CAPTURE_NOT_RECOMPUTED",
            "warning": "Indonesia bbox 격자 통계이며 공식 행정경계 평균·독립 관측 정답·미래 전망이 아닙니다.",
        }

    @app.get("/api/climate/contract")
    def contract():
        sample, proof = store.read_json("cckp", CCKP + "query-request.json")
        return {
            "status": "VERIFIED_REAL",
            "contract": tool_contract(),
            "sample": sample,
            "evidence": proof,
        }

    @app.post("/api/climate/query")
    def query_climate(body: ClimateQueryRequest):
        proof = store.check("cckp")
        lock = store._lock()
        license_sha = lock["groups"]["cckp"]["files"][CCKP + "license-evidence.json"]["sha256"]
        result = climate_query(
            body.model_dump(mode="json"),
            store.safe_path(CCKP + "global-asset.nc"),
            store.safe_path(CCKP + "raw-receipt.json"),
            license_evidence_path=store.safe_path(CCKP + "license-evidence.json"),
            license_evidence_sha256=license_sha,
        )
        return {
            "status": result["status"],
            "result": result,
            "evidence": proof,
            "mode": "LOCAL_PINNED_GRID_REPRODUCTION",
            "external_requests": 0,
        }

    @app.get("/api/klhk")
    def klhk():
        verified, proof = store.read_json("klhk", KLHK + "verification-20261124.json")
        report, _ = store.read_json("klhk", KLHK + "live-20261124-1/summary.json")
        return {
            "status": "BLOCKED",
            "evidence": proof,
            "acquisition": verified,
            "layers": report["klhk_discovery"],
            "blockers": [
                "NATIVE_23_CLASS_AND_LICENSE_NOT_VERIFIED",
                "RAG_PUBLICATION_NOT_APPROVED",
            ],
            "institution_authority_certified": False,
            "embedding_quality_verified": False,
        }

    @app.post("/api/rag/search")
    def rag(request: Request, body: RagRequest):
        decision = route_question(body.question)
        if body.scope == "mapbiomas-indonesia":
            check_local(request)
            return mapbiomas_document_answer(body.question)
        if decision.kind == "structured_climate_tool":
            return blocked(
                "NUMERIC_TOOL_REQUIRED",
                route="climate.query",
                answer=None,
                citations=[],
                missing_fields=list(decision.missing_fields),
            )
        proof = store.check("klhk")
        if curated_index is None:
            return blocked(
                "NO_AUTHORIZED_CURATED_INDEX",
                answer=None,
                citations=[],
                evidence=proof,
                warning="실제 문서 staging과 승인된 ACL/license/validity index는 다릅니다.",
            )
        # HTTP 사용자에게 역할을 입력받지 않는다. 현재 공개 익명 principal만 사용한다.
        result = curated_index.respond(
            SearchQuery(body.question, store.clock().astimezone(timezone.utc).date())
        )
        result["route"] = decision.kind
        result["index_scope"] = "TESTED_SYNTHETIC_INJECTED_INDEX"
        return result

    @app.get("/api/rag/mapbiomas/catalog")
    def mapbiomas_sources(request: Request):
        check_local(request)
        try:
            return geollm_storage.catalog()
        except StorageBlocked as error:
            return blocked(str(error), documents=[], structured_counts={})

    @app.post("/api/rag/mapbiomas/search")
    def mapbiomas_evidence(request: Request, body: RagRequest):
        check_local(request)
        return mapbiomas_document_answer(body.question)

    def mapbiomas_document_answer(question):
        if parse_question(question).metric not in ("document", "unknown"):
            return blocked("NUMERIC_TOOL_REQUIRED", route="/api/lcluc/geollm/query", answer=None, citations=[])
        return search_documents(geollm_storage, question)

    @app.get("/api/vector")
    def vector():
        report, proof = store.read_json(
            "vector", "evidence/vectorstore/climate-report-index-pinned.json"
        )
        path = store.safe_path("data/curated/vector/climate_reports_pinned.sqlite3")
        if Path(str(path) + "-wal").exists() and Path(str(path) + "-wal").stat().st_size:
            raise EvidenceBlocked("SQLITE_ACTIVE_WAL_NOT_PINNED")
        # mode=ro/immutable로 파일 생성·WAL 모드 변경·인덱싱을 하지 않는다.
        with sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True) as connection:
            count = connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        if (
            count != report.get("chunk_count")
            or report.get("database_sha256")
            != store._lock()["groups"]["vector"]["files"][
                "data/curated/vector/climate_reports_pinned.sqlite3"
            ]["sha256"]
        ):
            raise EvidenceBlocked("VECTOR_MANIFEST_DATABASE_DRIFT")
        return {
            "status": "IMPLEMENTED_UNVERIFIED",
            "backend": "SQLITE_LOCAL_PRIVATE_REVIEW",
            "pgvector_schema": "PRESENT_NOT_DEPLOYED",
            "document_count": report.get("document_count"),
            "chunk_count": count,
            "embedding_model": report.get("embedding_model"),
            "embedding_dimension": report.get("embedding_dimension"),
            "embedding_quality_verified": False,
            "access": report.get("access"),
            "public_search_enabled": False,
            "steward_auth_implemented": False,
            "blockers": ["LICENSE_RETRIEVAL_REVIEW_PENDING", "STEWARD_AUTH_NOT_IMPLEMENTED"],
            "evidence": proof,
        }

    @app.post("/api/reports/search")
    def report_search(body: RagRequest):
        if route_question(body.question).kind == "structured_climate_tool":
            return blocked(
                "NUMERIC_TOOL_REQUIRED", route="climate.query", answer=None, citations=[]
            )
        info = vector()
        return blocked(
            "PRIVATE_REVIEW_INDEX_AUTH_REQUIRED",
            backend=info["backend"],
            chunk_count=info["chunk_count"],
            answer=None,
            citations=[],
            public_search_enabled=False,
            warning="private data_steward index이며 인증 미구현 상태에서 검색하지 않습니다.",
        )

    @app.get("/api/sentinel")
    def sentinel():
        summary, proof = store.read_json("sentinel", SENTINEL + "handoff-summary-20261124.json")
        completeness, _ = store.read_json(
            "sentinel", SENTINEL + "held-audit-20261124/completeness.json"
        )
        # 객체 목록은 읽기 한도 내에서 검증하되 응답에는 합계만 전달한다.
        migration, _ = store.read_json(
            "sentinel", SENTINEL + "migration-receipt-20261124.json", max_bytes=8 * 1024 * 1024
        )
        post, _ = store.read_json("sentinel", SENTINEL + "post-migration-state-20261124.json")
        if (
            completeness.get("cell_count") != 36
            or len(completeness.get("cells", [])) != 36
            or migration.get("copied_objects") != post.get("local_CAS_files")
            or migration.get("unique_bytes") != post.get("local_CAS_bytes")
            or summary.get("migration_objects") != post.get("local_CAS_files")
            or summary.get("migration_bytes") != post.get("local_CAS_bytes")
        ):
            raise EvidenceBlocked("SENTINEL_REPORTS_INCONSISTENT")
        pilot_root = SENTINEL + "pilot-unit-20261124/"
        pilot, _ = store.read_json("sentinel", pilot_root + "run-01/result.json")
        final, _ = store.read_json("sentinel", pilot_root + "final-state.json")
        integrity, _ = store.read_json("sentinel", pilot_root + "postflight-integrity.json")
        events = pilot.get("http_events", [])
        if (
            len(events) != pilot["remote_request_count"]
            or sum(event["body_bytes"] for event in events) != pilot["remote_body_bytes_read"]
            or pilot["ledger_after_sha256"] != final["current_ledger_sha256"]
            or pilot["ledger_after_sha256"] != integrity["ledger_sha256_current"]
            or not integrity["quality_recomputed_from_native_SCL_matches"]
        ):
            raise EvidenceBlocked("PILOT_REPORTS_INCONSISTENT")
        audit, _ = store.read_json("sentinel", SENTINEL + "post-pilot-reaudit.json")
        if (
            audit["status"] != "VERIFIED_REAL"
            or audit["cell_count"] != completeness["cell_count"]
            or len(audit["cells"]) != audit["cell_count"]
            or audit["source_pins"]["baseline_report"] != summary["completeness_report_sha256"]
            or audit["source_pins"]["pilot_ledger_after"] != pilot["ledger_after_sha256"]
            or audit["source_pins"]["pilot_receipt"] != pilot["data_receipt_sha256"]
            or audit["pilot_delta"]["scene_id"] != pilot["scene_id"]
            or audit["next_collection"]["reference_window_observed_body_bytes"]
            != pilot["remote_body_bytes_read"]
        ):
            raise EvidenceBlocked("POST_PILOT_AUDIT_SOURCE_MISMATCH")
        queue = audit["missing_queue"]
        return {
            "status": "BLOCKED_COLLECTION_NOT_COMPLETE",
            "audit_state": "VERIFIED_REAL",
            "audited_cells": completeness["cell_count"],
            "expected_cells": 36,
            "completion": False,
            "full_spatial_coverage": audit["full_spatial_coverage"],
            "physical_patch_records": summary["physical_patch_records"],
            "quality_eligible_patches": summary["manifest_quality_eligible"],
            "verified_parent_frames": summary["verified_parent_frames"],
            "paired_six_band_same_scene_scl_coverage_pct": audit["weighted_present_coverage_pct"],
            "clear_coverage_pct": audit["weighted_clear_coverage_pct"],
            "area_audit_computed_at": audit["computed_at"],
            "missing_area_m2": audit["missing_area_m2"],
            "province_year_cells": audit["cells"],
            "next_collection": audit["next_collection"],
            "pilot_coverage_delta": audit["pilot_delta"],
            "grid_mode": completeness["grid_mode"],
            # 대형 GeoJSON은 열거나 전송하지 않는다. 감사 문서의 참조 메타데이터만 표시한다.
            "exact_missing_queue": {
                "sha256": queue["sha256"],
                "bytes": queue["bytes"],
                "features": queue["features"],
                "geometry_included": False,
            },
            "migration": {
                "status": migration["status"],
                "scope": migration["scope"],
                "cas_objects": post["local_CAS_files"],
                "cas_bytes": post["local_CAS_bytes"],
                "new_observation_acquisition": post["new_observation_acquisition"],
            },
            "pre_pilot_audit_remote_downloads": summary["remote_downloads"],
            "global_coverage_aggregate_updated": True,
            "coverage_basis": audit["coverage_basis"],
            "pilot": {
                "status": pilot["status"],
                "execution_status": pilot["execution_status"],
                "province": pilot["province"],
                "year": pilot["year"],
                "scene_id": pilot["scene_id"],
                "bands": [asset["band"] for asset in pilot["assets"]],
                "qa": pilot["qa"],
                "remote_body_bytes_read": pilot["remote_body_bytes_read"],
                "remote_request_count": pilot["remote_request_count"],
                "measurement_complete": pilot["measurement_complete"],
                "error_count": sum(event["http_status"] >= 400 for event in events),
                "observed_http429": any(event["http_status"] == 429 for event in events),
                "ledger_before_sha256": pilot["ledger_before_sha256"],
                "ledger_after_sha256": pilot["ledger_after_sha256"],
                "remaining_global_bytes": pilot["remaining_global_bytes"],
                "subsequent_pilots_started": final["additional_pilots_started"],
                "collector_count": final["collector_count"],
                "execution_lock_exists": integrity["legacy_execution_lock_exists"],
                "ledger_lock_exists": integrity["legacy_ledger_lock_exists"],
                "learning_ready": pilot["learning_ready"],
                "acceptance_blockers": pilot["acceptance_blockers"],
                "completed_at": pilot["completed_at"],
            },
            "runtime_snapshot": summary["runtime"],
            "reservation_adapter": "BOUNDED_PILOT_VERIFIED_NO_GENERAL_COLLECTION_AUTHORIZATION",
            # 감사 당시의 adapter/pin 미구현 blocker는 단일 pilot 경로 구현으로 해소됐다.
            # 일반 수집은 경계·예산 승인과 정확한 원격 창 고정이 필요하다.
            "blockers": [
                "GENERAL_COLLECTION_AUTHORIZATION_PENDING",
                "FULL_SPATIAL_COVERAGE_FALSE",
                "EXACT_SCENE_ASSET_WINDOW_PINS_MISSING",
                "COLLECTION_BUDGET_SUFFICIENCY_UNVERIFIED",
            ],
            "execution_started": False,
            "evidence": proof,
            "warning": "공간피복은 저장된 BIG 경계와 실제 보유 영상으로 계산했습니다. 전체 수집은 미완료입니다. 전송량은 256×256 시험 창의 본문 실측을 후보별 한 창에 적용한 계획값입니다. 독립 현장 정확도는 미측정입니다. 프로세스 수는 저장된 관측 시각 기준입니다.",
        }

    @app.get("/api/collection-progress")
    def collection_progress():
        return collection_snapshot(store, sentinel=sentinel, climate=cckp, vector=vector)

    @app.get("/api/models")
    def models():
        value, proof = store.read_json("models", "evidence/models/readiness.json")
        if not isinstance(value, dict) or not isinstance(value.get("models"), list):
            raise EvidenceBlocked("MODEL_CATALOG_INVALID")
        return {
            "status": value.get("status", "BLOCKED"),
            "models": value["models"],
            "legacy_checkpoint_audit": store.read_json(
                "models", "evidence/models/legacy-checkpoint-audit.json"
            )[0],
            "execution_started": False,
            "evidence": proof,
            "warning": "catalog 기록이 과학 검증·운영 배포 승인을 뜻하지 않습니다.",
        }

    @app.get("/api/gates")
    def gates():
        return blocked(
            "VERIFIED_TRAINING_DATA_AND_DEPLOYMENT_EVIDENCE_MISSING",
            policy=MLOpsPolicy().model_dump(),
            policy_authority="INTERNAL_PROPOSED_NOT_INSTITUTION_APPROVED",
            gates=[
                {"id": name, "status": "BLOCKED", "allowed": False, "reason": reason}
                for name, reason in (
                    ("training", "검증된 immutable dataset/split·6밴드/SCL·누수 gate 결과 미연결"),
                    (
                        "weak_agreement",
                        "약한 참조 일치도는 독립 정확도가 아니며 실제 평가 보고서 미연결",
                    ),
                    ("independent_accuracy", "독립 holdout·참조 SHA·평가자 보고서 미연결"),
                    ("human_approval", "검증된 사람 승인 ID 미연결"),
                    ("deployment", "모델·환경·보안·rollback·독립 정확도·사람 승인 미연결"),
                )
            ],
        )

    @app.post("/api/actions/{action}")
    def forbidden_action(action: str):
        return JSONResponse(blocked("EXECUTION_DISABLED_BY_DESIGN", action=action), status_code=409)

    @app.get("/api/workflow")
    def workflow():
        stages = []
        for group in ("cckp", "klhk", "sentinel", "models"):
            try:
                proof = store.check(group)
                status = "VERIFIED_REAL" if group == "cckp" else "BLOCKED"
                reason = "고정 증거 SHA 확인; 실행 gate와 별도"
            except EvidenceBlocked as error:
                proof = None
                status = "BLOCKED"
                reason = str(error)
            stages.append({"id": group, "status": status, "reason": reason, "evidence": proof})
        try:
            state, proof = store.read_json("workflow", "evidence/workflows/current-state.json")
            persisted = {
                "status": "IMPLEMENTED_UNVERIFIED",
                "state": WorkflowState.model_validate(state).model_dump(mode="json"),
                "evidence": proof,
            }
        except EvidenceBlocked as error:
            persisted = blocked(str(error))
        except ValidationError:
            persisted = blocked("WORKFLOW_STATE_SCHEMA_INVALID")
        try:
            result_registration = registration_snapshot(store)
        except EvidenceBlocked as error:
            result_registration = blocked(str(error))
        return {
            "status": "BLOCKED",
            "mode": "READ_ONLY_EVIDENCE_WORKFLOW",
            "stages": stages,
            "execution_started": False,
            "persisted_workflow": persisted,
            "result_registration": result_registration,
            "workflow_schema_status": "IMPLEMENTED_UNVERIFIED",
            "warning": "실제 Orchestrator Job 실행·진척률·학습·배포가 아닙니다.",
        }

    web = ROOT / "web"
    app.mount("/assets", StaticFiles(directory=web, check_dir=False), name="assets")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(web / "index.html")

    return app


app = create_app()
