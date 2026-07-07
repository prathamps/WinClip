"""Architecture boundary tests.

The hexagon's dependency rule, enforced in CI: the domain imports
nothing from the application or adapters, and the application core
never imports an adapter. Only ``bootstrap`` (the composition root)
and the adapters themselves may touch adapter code.
"""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "winclip"

FORBIDDEN = {
    "domain": ("winclip.application", "winclip.adapters", "winclip.bootstrap", "gi"),
    "application": ("winclip.adapters", "winclip.bootstrap", "gi"),
}


def imports_of(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            found.add("." * node.level + (node.module or ""))
    return found


@pytest.mark.parametrize("layer", sorted(FORBIDDEN))
def test_layer_respects_dependency_rule(layer):
    violations = []
    for py in (SRC / layer).rglob("*.py"):
        for imported in imports_of(py):
            if imported.startswith(FORBIDDEN[layer]):
                violations.append(f"{py.relative_to(SRC)} imports {imported}")
    assert not violations, "\n".join(violations)


def test_domain_uses_only_stdlib():
    allowed_prefixes = ("winclip.domain", ".", "__future__")
    stdlib = {"dataclasses", "datetime", "enum", "hashlib", "collections.abc", "typing"}
    for py in (SRC / "domain").rglob("*.py"):
        for imported in imports_of(py):
            ok = imported in stdlib or imported.startswith(allowed_prefixes)
            assert ok, f"{py.name} imports non-stdlib module {imported}"
