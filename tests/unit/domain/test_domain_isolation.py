"""Architecture test: the domain layer must depend on nothing but stdlib + pydantic."""
from __future__ import annotations

import ast
from pathlib import Path

import bharatai.domain as domain_pkg

FORBIDDEN = {
    "sqlite3",
    "sqlalchemy",
    "langgraph",
    "llama_index",
    "faiss",
    "paddleocr",
    "cv2",
    "streamlit",
    "ollama",
    "requests",
    "langchain",
}


def _domain_files() -> list[Path]:
    root = Path(domain_pkg.__file__).parent
    return sorted(root.rglob("*.py"))


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def test_domain_imports_no_forbidden_packages() -> None:
    for path in _domain_files():
        leaked = FORBIDDEN & _imported_roots(path)
        assert not leaked, f"{path.name} imports forbidden package(s): {leaked}"


def test_domain_only_imports_within_itself() -> None:
    for path in _domain_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            elif isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            for module in modules:
                if module.startswith("bharatai.") and not module.startswith("bharatai.domain"):
                    raise AssertionError(f"{path.name} imports non-domain module {module}")
