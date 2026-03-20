"""API tests for workspace-aware product list/detail/delete endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import ChatMessage, ChatSession, IngestionRun, Product, Review, Workspace
from app.db.session import get_db_session
from app.config import get_settings


def _build_app_with_db() -> tuple[TestClient, Session, object]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    from app.main import create_app

    app = create_app()

    def override_db_session():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db_session] = override_db_session
    return TestClient(app), Session(engine), app


def _seed_workspace(session: Session) -> uuid.UUID:
    workspace_id = uuid.uuid4()
    session.add(Workspace(id=workspace_id, name="Products Workspace"))
    session.commit()
    return workspace_id


def _seed_product_with_dependents(session: Session, workspace_id: uuid.UUID, *, name: str, with_dependents: bool = True) -> uuid.UUID:
    product_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    session.add(
        Product(
            id=product_id,
            workspace_id=workspace_id,
            platform="capterra",
            name=name,
            source_url="https://www.capterra.com/p/example/reviews/",
            stats={"total_reviews": 2, "average_rating": 4.5},
            created_at=now,
            updated_at=now,
        )
    )

    if with_dependents:
        run_id = uuid.uuid4()
        session.add(
            IngestionRun(
                id=run_id,
                workspace_id=workspace_id,
                product_id=product_id,
                source_type="scrape",
                status="success",
                outcome_code="ok",
                records_ingested=2,
                result_metadata={"message": "ok", "warnings": [], "diagnostics": {}},
                summary_snapshot={"total_reviews": 2},
                started_at=now,
                completed_at=now,
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            Review(
                workspace_id=workspace_id,
                product_id=product_id,
                ingestion_run_id=run_id,
                source_platform="capterra",
                review_fingerprint=f"fp-{product_id}",
                body="Great support and easy onboarding.",
                rating=4.5,
                author_name="Alex",
            )
        )

        chat_session_id = uuid.uuid4()
        session.add(
            ChatSession(
                id=chat_session_id,
                workspace_id=workspace_id,
                product_id=product_id,
                title="Session",
                started_at=now,
                last_activity_at=now,
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            ChatMessage(
                chat_session_id=chat_session_id,
                workspace_id=workspace_id,
                product_id=product_id,
                message_index=1,
                role="assistant",
                content="Grounded response.",
                is_refusal=False,
                message_metadata={"classification": "answer"},
                created_at=now,
            )
        )

    session.commit()
    return product_id


def test_products_list_returns_workspace_scoped_summary() -> None:
    client, verify_db, app = _build_app_with_db()
    workspace_id = _seed_workspace(verify_db)
    other_workspace_id = _seed_workspace(verify_db)

    _seed_product_with_dependents(verify_db, workspace_id, name="PressPage")
    _seed_product_with_dependents(verify_db, other_workspace_id, name="Other Product")

    response = client.get(
        "/products",
        params={"workspace_id": str(workspace_id)},
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["name"] == "PressPage"
    assert payload[0]["workspace_id"] == str(workspace_id)
    assert payload[0]["total_reviews"] == 1
    assert payload[0]["chat_session_count"] == 1
    assert payload[0]["latest_ingestion"]["status"] == "success"

    app.dependency_overrides.clear()
    verify_db.close()


def test_products_get_returns_detail_or_404() -> None:
    client, verify_db, app = _build_app_with_db()
    workspace_id = _seed_workspace(verify_db)
    product_id = _seed_product_with_dependents(verify_db, workspace_id, name="PressPage")

    ok = client.get(
        f"/products/{product_id}",
        params={"workspace_id": str(workspace_id)},
    )
    assert ok.status_code == 200
    detail = ok.json()
    assert detail["id"] == str(product_id)
    assert detail["name"] == "PressPage"
    assert detail["stats"]["average_rating"] == 4.5
    assert detail["latest_ingestion"]["status"] == "success"

    missing = client.get(
        f"/products/{uuid.uuid4()}",
        params={"workspace_id": str(workspace_id)},
    )
    assert missing.status_code == 404

    app.dependency_overrides.clear()
    verify_db.close()


def test_products_delete_removes_dependent_data_and_returns_404_after() -> None:
    client, verify_db, app = _build_app_with_db()
    workspace_id = _seed_workspace(verify_db)
    product_id = _seed_product_with_dependents(verify_db, workspace_id, name="PressPage")

    delete_response = client.delete(
        f"/products/{product_id}",
        params={"workspace_id": str(workspace_id)},
    )
    assert delete_response.status_code == 204

    verify = Session(verify_db.get_bind())
    assert verify.query(Product).filter(Product.id == product_id).count() == 0
    assert verify.query(Review).filter(Review.product_id == product_id).count() == 0
    assert verify.query(IngestionRun).filter(IngestionRun.product_id == product_id).count() == 0
    assert verify.query(ChatSession).filter(ChatSession.product_id == product_id).count() == 0
    assert verify.query(ChatMessage).filter(ChatMessage.product_id == product_id).count() == 0
    verify.close()

    detail_after_delete = client.get(
        f"/products/{product_id}",
        params={"workspace_id": str(workspace_id)},
    )
    assert detail_after_delete.status_code == 404

    app.dependency_overrides.clear()
    verify_db.close()


def test_products_delete_returns_404_for_missing_workspace_product_pair() -> None:
    client, verify_db, app = _build_app_with_db()
    workspace_id = _seed_workspace(verify_db)
    _ = _seed_workspace(verify_db)

    response = client.delete(
        f"/products/{uuid.uuid4()}",
        params={"workspace_id": str(workspace_id)},
    )
    assert response.status_code == 404

    app.dependency_overrides.clear()
    verify_db.close()


def test_products_list_isolated_by_workspace_cookie_across_clients() -> None:
    _client, verify_db, app = _build_app_with_db()
    workspace_one = _seed_workspace(verify_db)
    workspace_two = _seed_workspace(verify_db)

    _seed_product_with_dependents(verify_db, workspace_one, name="Workspace One Product")
    _seed_product_with_dependents(verify_db, workspace_two, name="Workspace Two Product")

    cookie_name = get_settings().workspace_cookie_name

    with TestClient(app) as client_one:
        client_one.cookies.set(cookie_name, str(workspace_one))
        response_one = client_one.get("/products")

    with TestClient(app) as client_two:
        client_two.cookies.set(cookie_name, str(workspace_two))
        response_two = client_two.get("/products")

    assert response_one.status_code == 200
    assert response_two.status_code == 200

    payload_one = response_one.json()
    payload_two = response_two.json()

    assert len(payload_one) == 1
    assert payload_one[0]["workspace_id"] == str(workspace_one)
    assert payload_one[0]["name"] == "Workspace One Product"

    assert len(payload_two) == 1
    assert payload_two[0]["workspace_id"] == str(workspace_two)
    assert payload_two[0]["name"] == "Workspace Two Product"

    app.dependency_overrides.clear()
    verify_db.close()


def test_products_cookie_isolation_smoke_with_cookie_issuance_and_reuse() -> None:
    _client, verify_db, app = _build_app_with_db()
    cookie_name = get_settings().workspace_cookie_name

    with TestClient(app) as client_a:
        first = client_a.get("/products")
        assert first.status_code == 200
        assert first.json() == []
        assert cookie_name in client_a.cookies
        workspace_a = uuid.UUID(client_a.cookies.get(cookie_name))

        _seed_product_with_dependents(verify_db, workspace_a, name="Cookie A Product")

        second = client_a.get("/products")
        assert second.status_code == 200
        assert len(second.json()) == 1
        assert second.json()[0]["name"] == "Cookie A Product"

    with TestClient(app) as client_b:
        first_b = client_b.get("/products")
        assert first_b.status_code == 200
        assert first_b.json() == []
        assert cookie_name in client_b.cookies
        workspace_b = uuid.UUID(client_b.cookies.get(cookie_name))

        assert workspace_b != workspace_a

        after_seed_a = client_b.get("/products")
        assert after_seed_a.status_code == 200
        assert after_seed_a.json() == []

    app.dependency_overrides.clear()
    verify_db.close()
