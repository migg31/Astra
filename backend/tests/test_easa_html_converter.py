from lxml import etree
from backend.harvest.easa_html_converter import HtmlConverter

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

def _make_para(text, style=None):
    p = etree.Element(f"{{{W}}}p")
    pPr = etree.SubElement(p, f"{{{W}}}pPr")
    if style:
        etree.SubElement(pPr, f"{{{W}}}pStyle", {f"{{{W}}}val": style})
    r = etree.SubElement(p, f"{{{W}}}r")
    t = etree.SubElement(r, f"{{{W}}}t")
    t.text = text
    return p

def test_block_wrapping():
    converter = HtmlConverter(image_rid_map={})
    
    # Mock SDT with a mix of styles
    sdt = etree.Element(f"{{{W}}}sdt")
    content = etree.SubElement(sdt, f"{{{W}}}sdtContent")
    
    content.append(_make_para("Rule 1", "ruletitle"))
    content.append(_make_para("Rule content"))
    content.append(_make_para("AMC 1", "amctitle"))
    content.append(_make_para("AMC content"))
    content.append(_make_para("GM 1", "gmtitle"))
    content.append(_make_para("GM content"))
    content.append(_make_para("Heading 2", "heading2"))
    content.append(_make_para("Outside content"))
    
    html = converter.sdt_to_html(sdt)
    
    # Check for presence of blocks
    assert '<div class="easa-block easa-rule">' in html
    assert '<h2>Rule 1</h2>' in html
    assert '<p>Rule content</p>' in html
    
    assert '</div>' in html
    assert '<div class="easa-block easa-amc">' in html
    assert '<h3>AMC 1</h3>' in html
    assert '<p>AMC content</p>' in html
    
    assert '<div class="easa-block easa-gm">' in html
    assert '<h3>GM 1</h3>' in html
    assert '<p>GM content</p>' in html
    
    assert '<h3>Heading 2</h3>' in html
    assert '<p>Outside content</p>' in html
    
    # Check that major heading closes blocks
    # Heading 2 should not be inside easa-gm
    parts = html.split('<div class="easa-block easa-gm">')
    assert len(parts) == 2
    gm_content = parts[1].split('</div>')[0]
    assert '<h3>GM 1</h3>' in gm_content
    assert '<h3>Heading 2</h3>' not in gm_content

def test_nested_sdt_flattening():
    converter = HtmlConverter(image_rid_map={})
    
    sdt = etree.Element(f"{{{W}}}sdt")
    content = etree.SubElement(sdt, f"{{{W}}}sdtContent")
    
    nested_sdt = etree.SubElement(content, f"{{{W}}}sdt")
    nested_content = etree.SubElement(nested_sdt, f"{{{W}}}sdtContent")
    nested_content.append(_make_para("AMC 1", "amctitle"))
    nested_content.append(_make_para("Nested content"))
    
    content.append(_make_para("Parent content"))
    
    html = converter.sdt_to_html(sdt)
    
    assert '<div class="easa-block easa-amc">' in html
    assert '<h3>AMC 1</h3>' in html
    assert '<p>Nested content</p>' in html
    assert '<p>Parent content</p>' in html
    assert html.count('</div>') == 1  # All elements should be in the same block
