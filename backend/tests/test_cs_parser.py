"""Test CS-25 and CS-ACNS parsing to ensure all expected nodes are created.

This test validates the fixes for missing nodes in CS documents:
- J-codes (25J901, etc.)
- Variant numbers (AMC2, GM3, etc.)
- Standalone appendices
- "AMC No. X to CS" format
- Bare codes classified as CS instead of IR
"""
from pathlib import Path

import pytest

from backend.harvest.easa_parser import parse_easa_xml


# These paths assume the XML files have been extracted from the ZIP archives
CS25_XML = Path(__file__).parent.parent.parent / "scratch" / "CS" / "extracted" / "CS-25 online publication Jan 23 fixes - xml (machine).xml"
CS_ACNS_XML = Path(__file__).parent.parent.parent / "scratch" / "CS" / "extracted" / "Easy Access Rules for Airborne Communications, Navigation and Surveillance (CS-ACNS).xml"


@pytest.mark.skipif(not CS25_XML.exists(), reason="CS-25 XML not available")
def test_cs25_node_count():
    """CS-25 should create at least 830 nodes (was 712 before fixes)."""
    result = parse_easa_xml(CS25_XML)
    assert len(result.nodes) >= 830, f"Expected >=830 nodes, got {len(result.nodes)}"
    
    # Check node type distribution
    by_type = {}
    for n in result.nodes:
        by_type[n.node_type] = by_type.get(n.node_type, 0) + 1
    
    assert by_type.get("CS", 0) >= 500, "Should have at least 500 CS nodes"
    assert by_type.get("AMC", 0) >= 320, "Should have at least 320 AMC nodes"
    assert by_type.get("IR", 0) == 0, "CS-25 should have no IR nodes (all should be CS)"


@pytest.mark.skipif(not CS25_XML.exists(), reason="CS-25 XML not available")
def test_cs25_j_codes():
    """CS-25 Subpart J codes (25J901, etc.) should be parsed correctly."""
    result = parse_easa_xml(CS25_XML)
    
    j_codes = [n for n in result.nodes if "25J" in n.reference_code]
    assert len(j_codes) >= 50, f"Expected at least 50 J-codes, got {len(j_codes)}"
    
    # Check specific J-codes
    j_refs = {n.reference_code for n in j_codes}
    assert "CS 25J901" in j_refs, "CS 25J901 (Installation) should be present"
    assert "CS 25J903" in j_refs, "CS 25J903 (APU) should be present"


@pytest.mark.skipif(not CS_ACNS_XML.exists(), reason="CS-ACNS XML not available")
def test_cs_acns_node_count():
    """CS-ACNS should create at least 500 nodes (was 444 before fixes)."""
    result = parse_easa_xml(CS_ACNS_XML)
    assert len(result.nodes) >= 500, f"Expected >=500 nodes, got {len(result.nodes)}"
    
    # Check node type distribution
    by_type = {}
    for n in result.nodes:
        by_type[n.node_type] = by_type.get(n.node_type, 0) + 1
    
    assert by_type.get("CS", 0) >= 240, "Should have at least 240 CS nodes"
    assert by_type.get("AMC", 0) >= 175, "Should have at least 175 AMC nodes"
    assert by_type.get("GM", 0) >= 80, "Should have at least 80 GM nodes"


@pytest.mark.skipif(not CS_ACNS_XML.exists(), reason="CS-ACNS XML not available")
def test_cs_acns_variant_numbers():
    """CS-ACNS variant numbers (AMC2, GM3, etc.) should be preserved in reference_code."""
    result = parse_easa_xml(CS_ACNS_XML)
    
    # Find nodes with variant numbers
    variants = [n for n in result.nodes if any(x in n.reference_code for x in ["AMC2", "AMC3", "GM2", "GM3"])]
    assert len(variants) >= 30, f"Expected at least 30 variant nodes, got {len(variants)}"
    
    # Check specific variants exist
    variant_refs = {n.reference_code for n in variants}
    assert "AMC2 ACNS.B.DLS.B1.025" in variant_refs, "AMC2 variant should be preserved"
    assert "AMC3 ACNS.B.DLS.B1.025" in variant_refs, "AMC3 variant should be preserved"
    assert "GM2 ACNS.B.DLS.B1.025" in variant_refs, "GM2 variant should be preserved"


@pytest.mark.skipif(not CS_ACNS_XML.exists(), reason="CS-ACNS XML not available")
def test_cs_acns_no_duplicates():
    """CS-ACNS should have no duplicate reference_code values."""
    result = parse_easa_xml(CS_ACNS_XML)
    
    from collections import Counter
    ref_counts = Counter(n.reference_code for n in result.nodes)
    duplicates = {k: v for k, v in ref_counts.items() if v > 1}
    
    assert len(duplicates) == 0, f"Found {len(duplicates)} duplicate reference codes: {list(duplicates.keys())[:5]}"


@pytest.mark.skipif(not CS25_XML.exists(), reason="CS-25 XML not available")
def test_cs25_amc_no_format():
    """CS-25 'AMC No. X to CS' format should be recognized."""
    result = parse_easa_xml(CS25_XML)
    
    # These specific AMC nodes use the "AMC No. X to CS" format
    refs = {n.reference_code for n in result.nodes}
    
    # At least some AMC nodes should exist (the exact reference depends on how we build it)
    amc_nodes = [n for n in result.nodes if n.node_type == "AMC" and "25.101" in n.reference_code]
    assert len(amc_nodes) >= 2, "Should have multiple AMC nodes for 25.101 (No. 1, No. 2, etc.)"


@pytest.mark.skipif(not CS25_XML.exists(), reason="CS-25 XML not available")
def test_cs25_appendices():
    """CS-25 standalone appendices should be parsed."""
    result = parse_easa_xml(CS25_XML)
    
    # Count appendix nodes
    appendix_nodes = [n for n in result.nodes if "Appendix" in n.reference_code or "APPENDIX" in n.reference_code]
    assert len(appendix_nodes) >= 30, f"Expected at least 30 appendix nodes, got {len(appendix_nodes)}"
