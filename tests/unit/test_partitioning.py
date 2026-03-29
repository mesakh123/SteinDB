"""Tests for partitioning rules."""

from __future__ import annotations

from steindb.rules.partitioning import (
    HashPartitionRule,
    ListPartitionRule,
    RangePartitionRule,
    SubpartitionRule,
)


class TestRangePartitionRule:
    rule = RangePartitionRule()

    def test_matches(self) -> None:
        sql = (
            "CREATE TABLE sales (id INT, amount INT) "
            "PARTITION BY RANGE (amount) "
            "(PARTITION p1 VALUES LESS THAN (100), "
            "PARTITION p2 VALUES LESS THAN (MAXVALUE));"
        )
        assert self.rule.matches(sql)

    def test_no_match(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (id INT);")

    def test_apply(self) -> None:
        sql = (
            "CREATE TABLE sales (id INT, amount INT) "
            "PARTITION BY RANGE (amount) "
            "(PARTITION p1 VALUES LESS THAN (100), "
            "PARTITION p2 VALUES LESS THAN (MAXVALUE));"
        )
        result = self.rule.apply(sql)
        assert "PARTITION BY RANGE (amount);" in result
        assert "CREATE TABLE p1 PARTITION OF sales" in result
        assert "FOR VALUES FROM (MINVALUE) TO (100);" in result
        assert "CREATE TABLE p2 PARTITION OF sales" in result
        assert "MAXVALUE" in result

    def test_apply_three_partitions(self) -> None:
        sql = (
            "CREATE TABLE orders (id INT, year INT) "
            "PARTITION BY RANGE (year) "
            "(PARTITION p2020 VALUES LESS THAN (2021), "
            "PARTITION p2021 VALUES LESS THAN (2022), "
            "PARTITION p_max VALUES LESS THAN (MAXVALUE));"
        )
        result = self.rule.apply(sql)
        assert "p2020" in result
        assert "p2021" in result
        assert "p_max" in result


class TestListPartitionRule:
    rule = ListPartitionRule()

    def test_matches(self) -> None:
        sql = (
            "CREATE TABLE regions (id INT, region VARCHAR(10)) "
            "PARTITION BY LIST (region) "
            "(PARTITION p_east VALUES ('NY','NJ'), "
            "PARTITION p_west VALUES ('CA','WA'));"
        )
        assert self.rule.matches(sql)

    def test_no_match(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (id INT);")

    def test_apply(self) -> None:
        sql = (
            "CREATE TABLE regions (id INT, region VARCHAR(10)) "
            "PARTITION BY LIST (region) "
            "(PARTITION p_east VALUES ('NY','NJ'), "
            "PARTITION p_west VALUES ('CA','WA'));"
        )
        result = self.rule.apply(sql)
        assert "PARTITION BY LIST (region);" in result
        assert "CREATE TABLE p_east PARTITION OF regions FOR VALUES IN ('NY','NJ');" in result
        assert "CREATE TABLE p_west PARTITION OF regions FOR VALUES IN ('CA','WA');" in result


class TestHashPartitionRule:
    rule = HashPartitionRule()

    def test_matches(self) -> None:
        sql = "CREATE TABLE logs (id INT, data TEXT) PARTITION BY HASH (id) PARTITIONS 4;"
        assert self.rule.matches(sql)

    def test_no_match(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (id INT);")

    def test_apply(self) -> None:
        sql = "CREATE TABLE logs (id INT, data TEXT) PARTITION BY HASH (id) PARTITIONS 4;"
        result = self.rule.apply(sql)
        assert "PARTITION BY HASH (id);" in result
        assert "MODULUS 4, REMAINDER 0" in result
        assert "MODULUS 4, REMAINDER 1" in result
        assert "MODULUS 4, REMAINDER 2" in result
        assert "MODULUS 4, REMAINDER 3" in result
        assert "logs_p0" in result
        assert "logs_p3" in result

    def test_apply_2_partitions(self) -> None:
        sql = "CREATE TABLE t (id INT) PARTITION BY HASH (id) PARTITIONS 2;"
        result = self.rule.apply(sql)
        lines = result.strip().split("\n")
        assert len(lines) == 3  # 1 create + 2 partitions


class TestSubpartitionRule:
    rule = SubpartitionRule()

    def test_matches(self) -> None:
        sql = (
            "CREATE TABLE t (id INT) "
            "PARTITION BY RANGE (id) "
            "SUBPARTITION BY HASH (id) "
            "PARTITIONS 4;"
        )
        assert self.rule.matches(sql)

    def test_no_match(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (id INT) PARTITION BY RANGE (id);")

    def test_apply_forwards_to_llm(self) -> None:
        sql = "CREATE TABLE t (id INT) SUBPARTITION BY HASH (id);"
        result = self.rule.apply(sql)
        assert "FORWARD TO LLM" in result
        assert "Original:" in result


class TestPartitionApplyNoMatch:
    """Cover early-return lines when apply() is called on non-matching SQL."""

    def test_range_apply_no_match(self) -> None:
        """Cover line 48: RangePartitionRule.apply returns sql unchanged."""
        rule = RangePartitionRule()
        sql = "CREATE TABLE t (id INT);"
        assert rule.apply(sql) == sql

    def test_list_apply_no_match(self) -> None:
        """Cover line 110: ListPartitionRule.apply returns sql unchanged."""
        rule = ListPartitionRule()
        sql = "CREATE TABLE t (id INT);"
        assert rule.apply(sql) == sql

    def test_hash_apply_no_match(self) -> None:
        """Cover line 160: HashPartitionRule.apply returns sql unchanged."""
        rule = HashPartitionRule()
        sql = "CREATE TABLE t (id INT);"
        assert rule.apply(sql) == sql
