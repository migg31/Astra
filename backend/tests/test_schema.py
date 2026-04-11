"""Schema smoke tests.

Each test wraps its writes in a transaction that is rolled back at teardown,
so the suite is non-destructive against whatever data already exists in the
database. This matters because the API tests below depend on the ingested
EASA Part 21 content being present.
"""
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from backend.database.connection import engine

EXPECTED_TABLES = {
    "harvest_sources",
    "harvest_documents",
    "harvest_document_versions",
    "regulatory_nodes",
    "regulatory_edges",
    "regulatory_changes",
}


async def test_expected_tables_exist():
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
        )
        tables = {row[0] for row in result}
    assert EXPECTED_TABLES.issubset(tables), f"missing: {EXPECTED_TABLES - tables}"


async def test_insert_nodes_and_edge():
    """Use reference_codes that won't collide with the ingested EASA data."""
    async with engine.connect() as conn:
        trans = await conn.begin()
        try:
            await conn.execute(
                text(
                    """
                    INSERT INTO regulatory_nodes
                        (node_type, reference_code, title, content_text, content_hash,
                         hierarchy_path)
                    VALUES
                        ('IR',  'TEST.IR.1', 'Test IR',
                         'irrelevant', 'hash-ir', 'Test/IR'),
                        ('AMC', 'TEST.AMC.1', 'Test AMC',
                         'irrelevant', 'hash-amc', 'Test/AMC')
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    INSERT INTO regulatory_edges (source_node_id, target_node_id, relation)
                    SELECT amc.node_id, ir.node_id, 'ACCEPTABLE_MEANS'
                    FROM regulatory_nodes amc, regulatory_nodes ir
                    WHERE amc.reference_code = 'TEST.AMC.1'
                      AND ir.reference_code  = 'TEST.IR.1'
                    """
                )
            )
            result = await conn.execute(
                text(
                    "SELECT relation FROM regulatory_edges e "
                    "JOIN regulatory_nodes s ON s.node_id = e.source_node_id "
                    "WHERE s.reference_code = 'TEST.AMC.1'"
                )
            )
            assert result.scalar_one() == "ACCEPTABLE_MEANS"
        finally:
            await trans.rollback()


async def test_self_edge_rejected():
    async with engine.connect() as conn:
        outer = await conn.begin()
        try:
            await conn.execute(
                text(
                    """
                    INSERT INTO regulatory_nodes
                        (node_type, reference_code, title, content_text, content_hash,
                         hierarchy_path)
                    VALUES
                        ('IR', 'TEST.SELF.1', 'self-edge target',
                         'x', 'h', 'Test/Self')
                    """
                )
            )
            # Use a nested savepoint so the failing INSERT rolls back cleanly
            # and the outer transaction stays usable.
            sp = await conn.begin_nested()
            with pytest.raises(IntegrityError):
                await conn.execute(
                    text(
                        """
                        INSERT INTO regulatory_edges (source_node_id, target_node_id, relation)
                        SELECT node_id, node_id, 'REFERENCES'
                        FROM regulatory_nodes WHERE reference_code = 'TEST.SELF.1'
                        """
                    )
                )
            await sp.rollback()
        finally:
            await outer.rollback()


async def test_unique_node_constraint():
    async with engine.connect() as conn:
        outer = await conn.begin()
        try:
            await conn.execute(
                text(
                    """
                    INSERT INTO regulatory_nodes
                        (node_type, reference_code, title, content_text, content_hash,
                         hierarchy_path)
                    VALUES
                        ('IR', 'TEST.UNIQUE.1', 'first',
                         'x', 'h1', 'Test/Unique')
                    """
                )
            )
            sp = await conn.begin_nested()
            with pytest.raises(IntegrityError):
                await conn.execute(
                    text(
                        """
                        INSERT INTO regulatory_nodes
                            (node_type, reference_code, title, content_text, content_hash,
                             hierarchy_path)
                        VALUES
                            ('IR', 'TEST.UNIQUE.1', 'duplicate',
                             'x', 'h2', 'Test/Unique/dup')
                        """
                    )
                )
            await sp.rollback()
        finally:
            await outer.rollback()
