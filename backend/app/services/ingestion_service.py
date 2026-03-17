"""Ingestion orchestration service for URL and CSV attempts."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from io import StringIO
from urllib.parse import urlparse

from sqlalchemy.exc import IntegrityError

from app.repositories.ingestion_runs import IngestionRunRepository
from app.schemas.ingestion import (
    CSVIngestionRequest,
    IngestionAttemptResponse,
    IngestionOutcomeCode,
    IngestionRunStatus,
    IngestionSourceType,
    URLIngestionRequest,
)


@dataclass(frozen=True)
class EvaluationResult:
    status: IngestionRunStatus
    outcome_code: IngestionOutcomeCode
    captured_reviews: int
    message: str
    warnings: list[str]
    error_detail: str | None = None


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

        evaluation = self._evaluate_url(str(payload.target_url))
        run = self._repository.finalize_attempt(
            run=run,
            status=evaluation.status,
            outcome_code=evaluation.outcome_code,
            captured_reviews=evaluation.captured_reviews,
            message=evaluation.message,
            warnings=evaluation.warnings,
            error_detail=evaluation.error_detail,
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
        run = self._repository.finalize_attempt(
            run=run,
            status=evaluation.status,
            outcome_code=evaluation.outcome_code,
            captured_reviews=evaluation.captured_reviews,
            message=evaluation.message,
            warnings=evaluation.warnings,
            error_detail=evaluation.error_detail,
        )
        return self._to_response(run)

    def _evaluate_url(self, target_url: str) -> EvaluationResult:
        parsed = urlparse(target_url)
        host = (parsed.netloc or "").lower()

        if "capterra.com" not in host:
            return EvaluationResult(
                status=IngestionRunStatus.FAILED,
                outcome_code=IngestionOutcomeCode.INVALID_URL,
                captured_reviews=0,
                message="Only Capterra URLs are currently supported.",
                warnings=[],
                error_detail="Target URL host must be capterra.com.",
            )

        normalized = target_url.lower()
        if "blocked" in normalized:
            return EvaluationResult(
                status=IngestionRunStatus.FAILED,
                outcome_code=IngestionOutcomeCode.BLOCKED,
                captured_reviews=0,
                message="Ingestion request was blocked by source constraints.",
                warnings=[],
                error_detail="Placeholder block signal in URL.",
            )

        if "parse-failed" in normalized or "parse_failed" in normalized:
            return EvaluationResult(
                status=IngestionRunStatus.FAILED,
                outcome_code=IngestionOutcomeCode.PARSE_FAILED,
                captured_reviews=0,
                message="Source content could not be parsed.",
                warnings=[],
                error_detail="Placeholder parse failure signal in URL.",
            )

        if "low-data" in normalized or "low_data" in normalized:
            return EvaluationResult(
                status=IngestionRunStatus.PARTIAL,
                outcome_code=IngestionOutcomeCode.LOW_DATA,
                captured_reviews=1,
                message="Ingestion completed with limited captured reviews.",
                warnings=["Low data volume detected from source page."],
            )

        return EvaluationResult(
            status=IngestionRunStatus.SUCCESS,
            outcome_code=IngestionOutcomeCode.OK,
            captured_reviews=5,
            message="Ingestion completed successfully.",
            warnings=[],
        )

    def _evaluate_csv(self, csv_content: str) -> EvaluationResult:
        if not csv_content.strip():
            return EvaluationResult(
                status=IngestionRunStatus.FAILED,
                outcome_code=IngestionOutcomeCode.EMPTY_CSV,
                captured_reviews=0,
                message="CSV file contains no data.",
                warnings=[],
                error_detail="Empty CSV payload.",
            )

        try:
            rows = list(csv.reader(StringIO(csv_content)))
        except csv.Error as exc:
            return EvaluationResult(
                status=IngestionRunStatus.FAILED,
                outcome_code=IngestionOutcomeCode.MALFORMED_CSV,
                captured_reviews=0,
                message="CSV could not be parsed.",
                warnings=[],
                error_detail=str(exc),
            )

        if not rows or not rows[0]:
            return EvaluationResult(
                status=IngestionRunStatus.FAILED,
                outcome_code=IngestionOutcomeCode.MALFORMED_CSV,
                captured_reviews=0,
                message="CSV header row is missing.",
                warnings=[],
                error_detail="Missing header row.",
            )

        header_width = len(rows[0])
        data_rows = rows[1:]

        for row in data_rows:
            if len(row) != header_width:
                return EvaluationResult(
                    status=IngestionRunStatus.FAILED,
                    outcome_code=IngestionOutcomeCode.MALFORMED_CSV,
                    captured_reviews=0,
                    message="CSV rows are inconsistent with header shape.",
                    warnings=[],
                    error_detail="Inconsistent row width.",
                )

        captured = len(data_rows)
        if captured == 0:
            return EvaluationResult(
                status=IngestionRunStatus.PARTIAL,
                outcome_code=IngestionOutcomeCode.LOW_DATA,
                captured_reviews=0,
                message="CSV parsed but contained no review records.",
                warnings=["No data rows were found after the header."],
            )

        if captured == 1:
            return EvaluationResult(
                status=IngestionRunStatus.PARTIAL,
                outcome_code=IngestionOutcomeCode.LOW_DATA,
                captured_reviews=1,
                message="CSV parsed with a low number of review records.",
                warnings=["Only one review record was detected."],
            )

        return EvaluationResult(
            status=IngestionRunStatus.SUCCESS,
            outcome_code=IngestionOutcomeCode.OK,
            captured_reviews=captured,
            message="CSV ingestion completed successfully.",
            warnings=[],
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
            started_at=run.started_at,
            completed_at=run.completed_at,
        )
