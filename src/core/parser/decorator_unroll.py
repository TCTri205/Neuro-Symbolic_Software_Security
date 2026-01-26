"""
Decorator Unrolling Utility for Flask/Django Routes

This module provides utilities to extract metadata from Python decorators,
particularly for web framework routing decorators like @app.route().
"""

import ast
from typing import Any, Dict, List, Optional


def extract_decorator_metadata(decorator: ast.expr) -> Dict[str, Any]:
    """
    Extract metadata from decorator expressions for unrolling.

    Handles common patterns:
    - @app.route('/path')
    - @app.route('/path', methods=['GET', 'POST'])
    - @route('/api/users', methods=['GET'], strict_slashes=False)
    - @staticmethod, @classmethod (simple decorators)

    Args:
        decorator: AST expression node representing the decorator

    Returns:
        Dictionary containing extracted metadata:
        - raw: unparsed string representation
        - type: decorator function name (e.g., 'route', 'post')
        - decorator_target: full target (e.g., 'app.route')
        - route_path: HTTP route path if applicable
        - methods: List of HTTP methods if specified
        - kwargs: Other keyword arguments
    """
    metadata: Dict[str, Any] = {
        "raw": ast.unparse(decorator),
        "type": None,
        "route_path": None,
        "methods": None,
        "kwargs": {},
    }

    if isinstance(decorator, ast.Call):
        func = decorator.func

        # Extract decorator type from attribute chain (e.g., app.route)
        if isinstance(func, ast.Attribute):
            metadata["type"] = func.attr  # e.g., "route"
            if isinstance(func.value, ast.Name):
                metadata["decorator_target"] = f"{func.value.id}.{func.attr}"
        elif isinstance(func, ast.Name):
            metadata["type"] = func.id
            metadata["decorator_target"] = func.id

        # Extract positional arguments (first arg is usually route path)
        if decorator.args:
            first_arg = decorator.args[0]
            if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                metadata["route_path"] = first_arg.value

        # Extract keyword arguments (methods, etc.)
        for keyword in decorator.keywords:
            key = keyword.arg
            value = keyword.value

            if key == "methods":
                # Extract HTTP methods list
                if isinstance(value, ast.List):
                    methods = []
                    for elt in value.elts:
                        if isinstance(elt, ast.Constant):
                            methods.append(elt.value)
                    metadata["methods"] = methods
                elif isinstance(value, ast.Constant):
                    metadata["methods"] = [value.value]
            else:
                # Store other keyword arguments
                try:
                    metadata["kwargs"][key] = ast.unparse(value)
                except Exception:
                    metadata["kwargs"][key] = str(value)

    # Handle simple decorators without calls (e.g., @staticmethod)
    elif isinstance(decorator, ast.Name):
        metadata["type"] = decorator.id
        metadata["decorator_target"] = decorator.id
    elif isinstance(decorator, ast.Attribute):
        metadata["type"] = decorator.attr
        if isinstance(decorator.value, ast.Name):
            metadata["decorator_target"] = f"{decorator.value.id}.{decorator.attr}"

    return metadata


def extract_all_decorators(decorator_list: List[ast.expr]) -> List[Dict[str, Any]]:
    """
    Extract metadata from all decorators in a list.

    Args:
        decorator_list: List of AST decorator expression nodes

    Returns:
        List of metadata dictionaries
    """
    return [extract_decorator_metadata(dec) for dec in decorator_list]


def is_route_decorator(metadata: Dict[str, Any]) -> bool:
    """
    Check if decorator metadata represents a routing decorator.

    Args:
        metadata: Decorator metadata dictionary

    Returns:
        True if this is a route decorator
    """
    if not metadata.get("type"):
        return False

    # Common routing decorator names
    route_types = {
        "route",
        "get",
        "post",
        "put",
        "delete",
        "patch",
        "head",
        "options",
        "trace",
        "connect",
    }

    decorator_type = metadata["type"].lower()
    return decorator_type in route_types or metadata.get("route_path") is not None


def get_route_info(metadata: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Extract route-specific information from decorator metadata.

    Args:
        metadata: Decorator metadata dictionary

    Returns:
        Dictionary with route information or None if not a route decorator
    """
    if not is_route_decorator(metadata):
        return None

    return {
        "path": metadata.get("route_path"),
        "methods": metadata.get("methods") or ["GET"],  # Default to GET
        "decorator_type": metadata.get("type"),
        "target": metadata.get("decorator_target"),
        "extra_kwargs": metadata.get("kwargs", {}),
    }
