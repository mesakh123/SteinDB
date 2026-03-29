"""Tests for complexity scoring -- Task 5."""

from steindb.cli.scanner.complexity import COMPLEXITY_FACTORS, ComplexityScorer, score_complexity
from steindb.contracts import ObjectType, ScannedObject


def test_none_and_empty():
    assert score_complexity(None) == 0.0
    assert score_complexity("") == 0.0


def test_simple_table_ddl():
    assert score_complexity("CREATE TABLE t (id NUMBER)") == 0.0


def test_connect_by():
    assert score_complexity("SELECT * FROM t CONNECT BY PRIOR id = pid") >= 2.0


def test_autonomous_transaction():
    assert score_complexity("PRAGMA AUTONOMOUS_TRANSACTION;") >= 3.0


def test_dbms_calls():
    assert score_complexity("DBMS_OUTPUT.PUT_LINE('x'); DBMS_LOB.CREATE(v);") >= 3.0


def test_model_clause():
    assert score_complexity("MODEL DIMENSION BY (y) MEASURES (a)") >= 4.0


def test_xmltype():
    assert score_complexity("v XMLTYPE := XMLTYPE('<a/>');") >= 2.0


def test_ref_cursor():
    assert score_complexity("TYPE rc IS REF CURSOR;") >= 1.5


def test_pipe_row():
    assert score_complexity("PIPE ROW(r);") >= 2.0


def test_sys_context():
    assert score_complexity("SYS_CONTEXT('USERENV', 'SESSION_ID')") >= 1.5


def test_dbms_lock():
    assert score_complexity("DBMS_LOCK.SLEEP(5);") >= 2.0


def test_utl_file():
    assert score_complexity("UTL_FILE.FOPEN('/tmp', 'f.txt', 'w');") >= 2.0


def test_dbms_aq():
    assert score_complexity("DBMS_AQ.ENQUEUE(queue_name => 'q1');") >= 3.0


def test_flashback():
    assert score_complexity("SELECT * FROM t AS OF FLASHBACK TIMESTAMP") >= 2.0


def test_combined_high_complexity():
    src = "AUTONOMOUS_TRANSACTION; CONNECT BY; MODEL; DBMS_OUTPUT; PIPE ROW; XMLTYPE"
    assert score_complexity(src) >= 7.0


def test_capped_at_10():
    assert score_complexity("CONNECT BY " * 100) <= 10.0


def test_case_insensitive():
    assert score_complexity("CONNECT BY") == score_complexity("connect by")


def test_factor_count_is_24():
    assert len(COMPLEXITY_FACTORS) == 24


class TestComplexityScorer:
    def test_scorer_returns_tuple(self):
        obj = ScannedObject(
            name="TEST",
            schema="HR",
            object_type=ObjectType.PROCEDURE,
            source_sql="BEGIN CONNECT BY PRIOR id = pid; END;",
            line_count=1,
        )
        scorer = ComplexityScorer()
        score, factors = scorer.score(obj)
        assert score >= 2.0
        assert len(factors) > 0

    def test_scorer_empty_source(self):
        obj = ScannedObject(
            name="TEST",
            schema="HR",
            object_type=ObjectType.TABLE,
            source_sql="CREATE TABLE t (id NUMBER)",
            line_count=1,
        )
        scorer = ComplexityScorer()
        score, factors = scorer.score(obj)
        assert score == 0.0
        assert factors == []
