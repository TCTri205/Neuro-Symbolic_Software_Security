import os
import ast
import json
from typing import Dict, Any, List
from src.core.cfg.builder import CFGBuilder
from src.core.cfg.ssa.transformer import SSATransformer

class Pipeline:
    def __init__(self):
        self.results = {}

    def scan_file(self, file_path: str):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
            
            tree = ast.parse(source, filename=file_path)
            
            builder = CFGBuilder()
            # Build CFG for the whole module
            cfg = builder.build(os.path.basename(file_path), tree)
            
            ssa = SSATransformer(cfg)
            ssa.analyze()
            
            self.results[file_path] = self._serialize(cfg, ssa)
            
        except Exception as e:
            self.results[file_path] = {"error": str(e)}

    def _serialize(self, cfg, ssa) -> Dict[str, Any]:
        blocks = []
        for block in cfg._blocks.values():
            # Simply count statements for summary
            # and list phis
            phis = [str(p) for p in block.phi_nodes]
            blocks.append({
                "id": block.id,
                "stmt_count": len(block.statements),
                "phis": phis
            })
            
        edges = []
        for u, v, data in cfg.graph.edges(data=True):
            edges.append({
                "source": u, 
                "target": v, 
                "label": data.get("label")
            })
            
        return {
            "name": cfg.name,
            "stats": {
                "block_count": len(cfg._blocks),
                "edge_count": len(cfg.graph.edges),
                "var_count": len(ssa.vars)
            },
            "structure": {
                "blocks": blocks,
                "edges": edges
            }
        }

    def scan_directory(self, dir_path: str):
        for root, dirs, files in os.walk(dir_path):
            for file in files:
                if file.endswith(".py"):
                    full_path = os.path.join(root, file)
                    self.scan_file(full_path)

def run_scan_pipeline(target: str) -> Dict[str, Any]:
    pipeline = Pipeline()
    if os.path.isfile(target):
        pipeline.scan_file(target)
    elif os.path.isdir(target):
        pipeline.scan_directory(target)
    return pipeline.results
