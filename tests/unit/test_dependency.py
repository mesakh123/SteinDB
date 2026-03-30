"""Tests for dependency analyzer -- DAG building, topological sort, cross-object patterns."""

from steindb.rules.dependency import DependencyAnalyzer


def test_fk_dependency_ordering():
    """Tables with FK references should be ordered: parent before child."""
    sql = (
        "CREATE TABLE orders ("
        "id NUMBER PRIMARY KEY, "
        "customer_id NUMBER REFERENCES customers(id));\n"
        "CREATE TABLE customers (id NUMBER PRIMARY KEY, name VARCHAR2(100));"
    )
    analyzer = DependencyAnalyzer()
    result = analyzer.analyze(sql)
    names = list(result.topological_order)
    assert names.index("customers") < names.index("orders")


def test_sequence_trigger_identity_pattern():
    """Sequence + BEFORE INSERT trigger pattern should be detected."""
    sql = (
        "CREATE SEQUENCE emp_seq START WITH 1 INCREMENT BY 1;\n"
        "CREATE TABLE employees (id NUMBER PRIMARY KEY, name VARCHAR2(100));\n"
        "CREATE OR REPLACE TRIGGER emp_bi BEFORE INSERT ON employees "
        "FOR EACH ROW BEGIN SELECT emp_seq.NEXTVAL INTO :NEW.id FROM DUAL; END;\n/\n"
    )
    analyzer = DependencyAnalyzer()
    result = analyzer.analyze(sql)
    assert len(result.patterns) >= 1
    pattern = result.patterns[0]
    assert pattern["type"] == "sequence_trigger_identity"
    assert pattern["table"] == "employees"


def test_circular_dependency_detected():
    """Circular FK references should be detected and reported."""
    sql = (
        "CREATE TABLE a (id NUMBER PRIMARY KEY, b_id NUMBER REFERENCES b(id));\n"
        "CREATE TABLE b (id NUMBER PRIMARY KEY, a_id NUMBER REFERENCES a(id));"
    )
    analyzer = DependencyAnalyzer()
    result = analyzer.analyze(sql)
    assert len(result.circular) > 0


def test_empty_input():
    """Empty input should return empty graph."""
    analyzer = DependencyAnalyzer()
    result = analyzer.analyze("")
    assert len(result.topological_order) == 0


def test_single_table_no_deps():
    """Single table with no dependencies."""
    sql = "CREATE TABLE t (id NUMBER PRIMARY KEY, name VARCHAR2(100));"
    analyzer = DependencyAnalyzer()
    result = analyzer.analyze(sql)
    assert result.topological_order == ["t"]
    assert len(result.edges) == 0


def test_view_depends_on_table():
    """View should come after the table it references."""
    sql = "CREATE VIEW v AS SELECT * FROM t;\nCREATE TABLE t (id NUMBER PRIMARY KEY);"
    analyzer = DependencyAnalyzer()
    result = analyzer.analyze(sql)
    names = result.topological_order
    assert names.index("t") < names.index("v")


def test_trigger_depends_on_table():
    """Trigger should come after its target table."""
    sql = (
        "CREATE OR REPLACE TRIGGER trg BEFORE INSERT ON t FOR EACH ROW BEGIN NULL; END;\n/\n"
        "CREATE TABLE t (id NUMBER PRIMARY KEY);"
    )
    analyzer = DependencyAnalyzer()
    result = analyzer.analyze(sql)
    names = result.topological_order
    assert names.index("t") < names.index("trg")


def test_multiple_fk_chain():
    """Three-level FK chain should be ordered correctly."""
    sql = (
        "CREATE TABLE order_items (id NUMBER PRIMARY KEY, order_id NUMBER REFERENCES orders(id));\n"
        "CREATE TABLE orders ("
        "id NUMBER PRIMARY KEY, "
        "customer_id NUMBER REFERENCES customers(id));\n"
        "CREATE TABLE customers (id NUMBER PRIMARY KEY);"
    )
    analyzer = DependencyAnalyzer()
    result = analyzer.analyze(sql)
    names = result.topological_order
    assert names.index("customers") < names.index("orders")
    assert names.index("orders") < names.index("order_items")
