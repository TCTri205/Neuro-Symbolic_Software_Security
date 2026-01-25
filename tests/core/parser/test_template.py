from src.core.parser.template import TemplateParser

def test_parse_variables():
    content = """
    <h1>Hello {{ user.name }}</h1>
    <p>{{ content | safe }}</p>
    """
    parser = TemplateParser()
    nodes = parser.parse(content)
    
    vars = [n for n in nodes if n.node_type == 'variable']
    assert len(vars) == 2
    
    assert vars[0].expression == "user.name"
    assert vars[0].is_safe == False
    
    assert vars[1].expression == "content"
    assert vars[1].is_safe == True
    assert "safe" in vars[1].filters

def test_detect_ssti_patterns():
    content = """
    {{ user.__class__.__mro__ }}
    {{ config.items() }}
    """
    parser = TemplateParser()
    nodes = parser.parse(content)
    
    ssti_nodes = parser.scan_for_ssti(nodes)
    assert len(ssti_nodes) == 2
    assert "user.__class__.__mro__" in ssti_nodes[0].raw
    assert "config.items()" in ssti_nodes[1].raw

def test_django_block():
    content = "{% if user.is_authenticated %}Welcome{% endif %}"
    parser = TemplateParser()
    nodes = parser.parse(content)
    
    blocks = [n for n in nodes if n.node_type == 'block']
    assert len(blocks) == 2
    assert blocks[0].expression == "if user.is_authenticated"
    assert blocks[1].expression == "endif"
