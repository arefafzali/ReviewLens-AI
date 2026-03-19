"""Ingestion orchestration service for URL and CSV attempts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.repositories.ingestion_runs import IngestionRunRepository
from app.schemas.ingestion import (
    CSVIngestionRequest,
    IngestionAttemptResponse,
    IngestionOutcomeCode,
    IngestionRunStatus,
    IngestionSourceType,
    URLIngestionRequest,
)
from app.services.ingestion.csv_parser import CSVParseError, CSVParseErrorCode, parse_csv_reviews
from app.services.ingestion.url_pipeline import URLIngestionPipeline


@dataclass(frozen=True)
class EvaluationResult:
    status: IngestionRunStatus
    outcome_code: IngestionOutcomeCode
    captured_reviews: int
    message: str
    warnings: list[str]
    error_detail: str | None = None
    diagnostics: dict[str, Any] | None = None
    extracted_reviews: list[dict[str, Any]] | None = None


class IngestionOrchestrationService:
    """Coordinates ingestion run persistence and outcome modeling."""

    def __init__(self, repository: IngestionRunRepository) -> None:
        self._repository = repository

    def attempt_url_ingestion(self, payload: URLIngestionRequest) -> IngestionAttemptResponse:
        try:
            run = self._repository.create_attempt(
                workspace_id=payload.workspace_id,
                product_id=payload.product_id,
                source_type=IngestionSourceType.SCRAPE,
                target_url=str(payload.target_url),
                csv_filename=None,
            )
        except IntegrityError as exc:
            raise ValueError("workspace_id and product_id must reference existing records") from exc

        if not payload.reload:
            cached = self._repository.find_cached_url_ingestion(
                workspace_id=payload.workspace_id,
                product_id=payload.product_id,
                target_url=str(payload.target_url),
            )
            if cached is not None:
                source_diagnostics = dict(cached.get("source_diagnostics", {}))
                diagnostics = {
                    "cache_hit": True,
                    "cache_source_ingestion_run_id": str(cached["source_ingestion_run_id"]),
                    "cached_reviews": int(cached["cached_reviews"]),
                    "requested_url": str(payload.target_url),
                    "source_host": source_diagnostics.get("source_host"),
                    "provider": source_diagnostics.get("provider"),
                    "parser": source_diagnostics.get("parser"),
                    "reload": False,
                }
                run = self._repository.finalize_attempt(
                    run=run,
                    status=IngestionRunStatus.SUCCESS,
                    outcome_code=IngestionOutcomeCode.OK,
                    captured_reviews=int(cached["cached_reviews"]),
                    message="Ingestion served from cached stored reviews.",
                    warnings=[],
                    error_detail=None,
                    diagnostics=diagnostics,
                )
                return self._to_response(run)

        evaluation = self._evaluate_url(str(payload.target_url))
        persistence_stats = None
        if evaluation.extracted_reviews:
            persistence_stats = self._repository.persist_extracted_reviews(
                workspace_id=payload.workspace_id,
                product_id=payload.product_id,
                ingestion_run_id=run.id,
                source_host=(evaluation.diagnostics or {}).get("source_host"),
                reviews=evaluation.extracted_reviews,
            )
            captured_reviews = (
                persistence_stats.inserted_reviews
                if persistence_stats.inserted_reviews > 0
                else evaluation.captured_reviews
            )
            diagnostics = dict(evaluation.diagnostics or {})
            diagnostics["cache_hit"] = False
            diagnostics["reload"] = payload.reload
            diagnostics["persisted_reviews"] = persistence_stats.inserted_reviews
            diagnostics["extracted_reviews"] = evaluation.captured_reviews
            diagnostics["duplicates_removed"] = persistence_stats.duplicates_removed
            diagnostics["skipped_missing_body"] = persistence_stats.skipped_missing_body
            evaluation = EvaluationResult(
                status=evaluation.status,
                outcome_code=evaluation.outcome_code,
                captured_reviews=captured_reviews,
                message=evaluation.message,
                warnings=evaluation.warnings,
                error_detail=evaluation.error_detail,
                diagnostics=diagnostics,
                extracted_reviews=evaluation.extracted_reviews,
            )
        elif evaluation.diagnostics is not None:
            diagnostics = dict(evaluation.diagnostics)
            diagnostics["cache_hit"] = False
            diagnostics["reload"] = payload.reload
            evaluation = EvaluationResult(
                status=evaluation.status,
                outcome_code=evaluation.outcome_code,
                captured_reviews=evaluation.captured_reviews,
                message=evaluation.message,
                warnings=evaluation.warnings,
                error_detail=evaluation.error_detail,
                diagnostics=diagnostics,
                extracted_reviews=evaluation.extracted_reviews,
            )

        summary_snapshot: dict[str, Any] | None = None
        if evaluation.status == IngestionRunStatus.SUCCESS:
            analytics = self._repository.compute_and_store_ingestion_analytics(
                workspace_id=payload.workspace_id,
                product_id=payload.product_id,
                ingestion_run_id=run.id,
            )
            summary_snapshot = analytics.summary_snapshot
            diagnostics = dict(evaluation.diagnostics or {})
            diagnostics["analytics_generated"] = True
            diagnostics["summary_total_reviews"] = summary_snapshot.get("total_reviews", 0)
            evaluation = EvaluationResult(
                status=evaluation.status,
                outcome_code=evaluation.outcome_code,
                captured_reviews=evaluation.captured_reviews,
                message=evaluation.message,
                warnings=evaluation.warnings,
                error_detail=evaluation.error_detail,
                diagnostics=diagnostics,
                extracted_reviews=evaluation.extracted_reviews,
            )

        run = self._repository.finalize_attempt(
            run=run,
            status=evaluation.status,
            outcome_code=evaluation.outcome_code,
            captured_reviews=evaluation.captured_reviews,
            message=evaluation.message,
            warnings=evaluation.warnings,
            error_detail=evaluation.error_detail,
            diagnostics=evaluation.diagnostics,
            summary_snapshot=summary_snapshot,
        )
        return self._to_response(run)

    def attempt_csv_ingestion(self, payload: CSVIngestionRequest) -> IngestionAttemptResponse:
        try:
            run = self._repository.create_attempt(
                workspace_id=payload.workspace_id,
                product_id=payload.product_id,
                source_type=IngestionSourceType.CSV_UPLOAD,
                target_url=None,
                csv_filename=payload.csv_filename,
            )
        except IntegrityError as exc:
            raise ValueError("workspace_id and product_id must reference existing records") from exc

        evaluation = self._evaluate_csv(payload.csv_content)
        if evaluation.extracted_reviews:
            persistence_stats = self._repository.persist_extracted_reviews(
                workspace_id=payload.workspace_id,
                product_id=payload.product_id,
                ingestion_run_id=run.id,
                source_host="csv_upload",
                reviews=evaluation.extracted_reviews,
            )
            captured_reviews = (
                persistence_stats.inserted_reviews
                if persistence_stats.inserted_reviews > 0
                else evaluation.captured_reviews
            )
            diagnostics = dict(evaluation.diagnostics or {})
            diagnostics["persisted_reviews"] = persistence_stats.inserted_reviews
            diagnostics["parsed_reviews"] = evaluation.captured_reviews
            diagnostics["duplicates_removed"] = persistence_stats.duplicates_removed
            diagnostics["skipped_missing_body"] = persistence_stats.skipped_missing_body
            evaluation = EvaluationResult(
                status=evaluation.status,
                outcome_code=evaluation.outcome_code,
                captured_reviews=captured_reviews,
                message=evaluation.message,
                warnings=evaluation.warnings,
                error_detail=evaluation.error_detail,
                diagnostics=diagnostics,
                extracted_reviews=evaluation.extracted_reviews,
            )

        summary_snapshot: dict[str, Any] | None = None
        if evaluation.status == IngestionRunStatus.SUCCESS:
            analytics = self._repository.compute_and_store_ingestion_analytics(
                workspace_id=payload.workspace_id,
                product_id=payload.product_id,
                ingestion_run_id=run.id,
            )
            summary_snapshot = analytics.summary_snapshot
            diagnostics = dict(evaluation.diagnostics or {})
            diagnostics["analytics_generated"] = True
            diagnostics["summary_total_reviews"] = summary_snapshot.get("total_reviews", 0)
            evaluation = EvaluationResult(
                status=evaluation.status,
                outcome_code=evaluation.outcome_code,
                captured_reviews=evaluation.captured_reviews,
                message=evaluation.message,
                warnings=evaluation.warnings,
                error_detail=evaluation.error_detail,
                diagnostics=diagnostics,
                extracted_reviews=evaluation.extracted_reviews,
            )

        run = self._repository.finalize_attempt(
            run=run,
            status=evaluation.status,
            outcome_code=evaluation.outcome_code,
            captured_reviews=evaluation.captured_reviews,
            message=evaluation.message,
            warnings=evaluation.warnings,
            error_detail=evaluation.error_detail,
            diagnostics=evaluation.diagnostics,
            summary_snapshot=summary_snapshot,
        )
        return self._to_response(run)

    def _evaluate_url(self, target_url: str) -> EvaluationResult:
        settings = get_settings()
        pipeline = URLIngestionPipeline.with_firecrawl(
            firecrawl_api_key=settings.firecrawl_api_key,
            openai_api_key=settings.openai_api_key,
            openai_model=settings.openai_model,
            firecrawl_timeout_seconds=settings.firecrawl_timeout_seconds,
            openai_timeout_seconds=settings.openai_timeout_seconds,
            chunk_size_chars=settings.markdown_chunk_size_chars,
            chunk_overlap_chars=settings.markdown_chunk_overlap_chars,
            max_chunks=settings.markdown_max_chunks,
        )
        result = pipeline.run(target_url)
        return EvaluationResult(
            status=result.status,
            outcome_code=result.outcome_code,
            captured_reviews=result.captured_reviews,
            message=result.message,
            warnings=result.warnings,
            error_detail=result.error_detail,
            diagnostics=result.diagnostics,
            extracted_reviews=result.extracted_reviews,
        )

    def _evaluate_csv(self, csv_content: str) -> EvaluationResult:
        try:
            parsed = parse_csv_reviews(csv_content)
        except CSVParseError as exc:
            outcome = (
                IngestionOutcomeCode.EMPTY_CSV
                if exc.code == CSVParseErrorCode.EMPTY_INPUT
                else IngestionOutcomeCode.MALFORMED_CSV
            )
            return EvaluationResult(
                status=IngestionRunStatus.FAILED,
                outcome_code=outcome,
                captured_reviews=0,
                message="CSV could not be parsed." if outcome == IngestionOutcomeCode.MALFORMED_CSV else "CSV file contains no data.",
                warnings=[],
                error_detail=exc.detail,
            )

        captured = len(parsed.reviews)
        if captured == 0:
            return EvaluationResult(
                status=IngestionRunStatus.PARTIAL,
                outcome_code=IngestionOutcomeCode.LOW_DATA,
                captured_reviews=0,
                message="CSV parsed but contained no review records.",
                warnings=["No data rows were found after the header."],
                diagnostics={
                    "parser": "csv_alias_mapping",
                    "column_mapping": parsed.column_mapping,
                },
                extracted_reviews=[],
            )

        if captured == 1:
            return EvaluationResult(
                status=IngestionRunStatus.PARTIAL,
                outcome_code=IngestionOutcomeCode.LOW_DATA,
                captured_reviews=1,
                message="CSV parsed with a low number of review records.",
                warnings=["Only one review record was detected."],
                diagnostics={
                    "parser": "csv_alias_mapping",
                    "column_mapping": parsed.column_mapping,
                },
                extracted_reviews=parsed.reviews,
            )

        return EvaluationResult(
            status=IngestionRunStatus.SUCCESS,
            outcome_code=IngestionOutcomeCode.OK,
            captured_reviews=captured,
            message="CSV ingestion completed successfully.",
            warnings=[],
            diagnostics={
                "parser": "csv_alias_mapping",
                "column_mapping": parsed.column_mapping,
            },
            extracted_reviews=parsed.reviews,
        )

    def _to_response(self, run) -> IngestionAttemptResponse:
        metadata = run.result_metadata or {}
        return IngestionAttemptResponse(
            ingestion_run_id=run.id,
            source_type=IngestionSourceType(run.source_type),
            status=IngestionRunStatus(run.status),
            outcome_code=IngestionOutcomeCode(run.outcome_code),
            captured_reviews=run.records_ingested,
            message=str(metadata.get("message", "")),
            warnings=[str(item) for item in metadata.get("warnings", [])],
            diagnostics=dict(metadata.get("diagnostics", {})),
            started_at=run.started_at,
            completed_at=run.completed_at,
        )
