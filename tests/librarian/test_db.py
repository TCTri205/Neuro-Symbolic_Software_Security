import os
import pytest
import sqlite3
from src.librarian.db import LibrarianDB


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "test_librarian.db"
    return str(path)


@pytest.fixture
def librarian_db(db_path):
    return LibrarianDB(db_path)


def test_init_db(librarian_db, db_path):
    assert os.path.exists(db_path)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check tables exist
    tables = [
        "decisions",
        "vulnerability_types",
        "remediation_strategies",
        "library_profiles",
    ]
    for table in tables:
        cursor.execute(
            f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'"
        )
        assert cursor.fetchone() is not None

    conn.close()


def test_knowledge_graph_population(librarian_db):
    # Test adding vulnerability type
    librarian_db.add_vulnerability_type(
        id="test.vuln",
        name="Test Vuln",
        description="A test vulnerability",
        owasp_category="A00:Test",
        cwe_id="CWE-000",
    )

    # Test adding remediation strategy
    librarian_db.add_remediation_strategy(
        vulnerability_type_id="test.vuln",
        strategy_name="Fix it",
        description="Just fix it",
        code_template="fixed()",
    )

    # Verify in DB
    conn = sqlite3.connect(librarian_db.db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM vulnerability_types WHERE id = 'test.vuln'")
    vuln = cursor.fetchone()
    assert vuln is not None
    assert vuln[1] == "Test Vuln"  # name

    cursor.execute(
        "SELECT * FROM remediation_strategies WHERE vulnerability_type_id = 'test.vuln'"
    )
    rem = cursor.fetchone()
    assert rem is not None
    assert rem[2] == "Fix it"  # strategy_name

    conn.close()


def test_semantic_lookup(librarian_db):
    # Store a decision
    context_hash = "hash123"
    snippet_hash = "code_hash_456"
    check_id = "test.check"

    analysis_data = [
        {
            "check_id": check_id,
            "verdict": "VULNERABLE",
            "rationale": "Bad code",
            "remediation": "Fix code",
        }
    ]

    librarian_db.store_decision(
        context_hash=context_hash,
        analysis=analysis_data,
        raw_response="raw",
        model="test-model",
        snippet_hash=snippet_hash,
    )

    # Lookup by snippet hash (Semantic/Reuse)
    found = librarian_db.find_decision(check_id, snippet_hash)
    assert found is not None
    assert found["verdict"] == "VULNERABLE"
    assert found["check_id"] == check_id

    # Lookup with wrong hash should fail
    not_found = librarian_db.find_decision(check_id, "wrong_hash")
    assert not_found is None


def test_store_decision_updates(librarian_db):
    context_hash = "hash_update"
    librarian_db.store_decision(context_hash, [{"verdict": "SAFE"}], "raw1", "model1")

    # Update same hash
    librarian_db.store_decision(
        context_hash, [{"verdict": "VULNERABLE"}], "raw2", "model2"
    )

    decision = librarian_db.get_decision(context_hash)
    assert decision["verdict"] == "VULNERABLE"
    assert decision["raw_response"] == "raw2"
