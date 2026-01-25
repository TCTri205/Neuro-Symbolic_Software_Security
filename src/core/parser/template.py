import re
from typing import List, Set
from pydantic import BaseModel, Field

class TemplateNode(BaseModel):
    raw: str
    expression: str
    line: int
    start_col: int
    end_col: int
    node_type: str = Field(..., description="Type of node: 'variable', 'block', 'comment'")
    is_safe: bool = Field(False, description="True if marked safe explicitly (e.g. | safe)")
    filters: List[str] = Field(default_factory=list)

class TemplateParser:
    """
    Parser for Jinja2 and Django templates.
    Extracts variables and identifies potential sinks.
    """
    
    # Regex patterns
    VAR_PATTERN = re.compile(r'\{\{\s*(.*?)\s*\}\}')
    BLOCK_PATTERN = re.compile(r'\{%\s*(.*?)\s*%\}')
    COMMENT_PATTERN = re.compile(r'\{#.*?#\}')

    def parse(self, content: str) -> List[TemplateNode]:
        """
        Parse template content and return a list of nodes.
        """
        nodes = []
        lines = content.split('\n')
        
        for line_idx, line_content in enumerate(lines):
            line_num = line_idx + 1
            
            # Find variables {{ ... }}
            for match in self.VAR_PATTERN.finditer(line_content):
                raw = match.group(0)
                expr = match.group(1).strip()
                
                # Analyze filters
                filters = []
                is_safe = False
                
                if '|' in expr:
                    parts = expr.split('|')
                    base_expr = parts[0].strip()
                    filter_parts = [p.strip() for p in parts[1:]]
                    filters = filter_parts
                    
                    # Check for safety markers
                    for f in filter_parts:
                        if f == 'safe' or f == 'mark_safe':
                            is_safe = True
                else:
                    base_expr = expr

                nodes.append(TemplateNode(
                    raw=raw,
                    expression=base_expr,
                    line=line_num,
                    start_col=match.start(),
                    end_col=match.end(),
                    node_type='variable',
                    is_safe=is_safe,
                    filters=filters
                ))

            # Find blocks {% ... %} - mainly for context, not usually direct sinks (except include/extends)
            for match in self.BLOCK_PATTERN.finditer(line_content):
                nodes.append(TemplateNode(
                    raw=match.group(0),
                    expression=match.group(1).strip(),
                    line=line_num,
                    start_col=match.start(),
                    end_col=match.end(),
                    node_type='block'
                ))

        return nodes

    def scan_for_ssti(self, nodes: List[TemplateNode]) -> List[TemplateNode]:
        """
        Identify nodes that are potential SSTI candidates.
        In modern Jinja2/Django, SSTI usually happens if:
        1. The template ITSELF is created from user input (not handled here, that's Python side).
        2. Dangerous attributes are accessed in the template (e.g. .__class__, .mro, config.items).
        """
        ssti_nodes = []
        dangerous_keywords = ['__class__', '__mro__', '__subclasses__', 'config.items', 'self.__dict__']
        
        for node in nodes:
            if node.node_type == 'variable':
                for kw in dangerous_keywords:
                    if kw in node.expression:
                        ssti_nodes.append(node)
                        break
        return ssti_nodes
