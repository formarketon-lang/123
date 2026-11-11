"""Architecture boundary tests for TradeLab Pro."""

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIRECTORY = PROJECT_ROOT / "data"
CORE_DIRECTORY = PROJECT_ROOT / "core"


def _find_forbidden_imports(directory, forbidden_roots):
    violations = []

    for python_file in directory.rglob("*.py"):
        source = python_file.read_text(encoding="utf-8")
        syntax_tree = ast.parse(source, filename=str(python_file))

        for node in ast.walk(syntax_tree):
            imported_modules = []

            if isinstance(node, ast.Import):
                imported_modules.extend(
                    alias.name for alias in node.names
                )

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported_modules.append(node.module)

            for module in imported_modules:
                root = module.split(".", 1)[0]

                if root in forbidden_roots:
                    violations.append(
                        f"{python_file.relative_to(PROJECT_ROOT)}:"
                        f"{node.lineno} imports {module}"
                    )

    return violations


def test_data_layer_does_not_import_scripts():
    violations = _find_forbidden_imports(
        DATA_DIRECTORY, {"scripts"}
    )
    assert not violations, "\n".join(violations)


def test_data_layer_does_not_import_upper_layers():
    violations = _find_forbidden_imports(
        DATA_DIRECTORY, {"core", "ui"}
    )
    assert not violations, "\n".join(violations)


def test_core_layer_does_not_import_ui_or_scripts():
    violations = _find_forbidden_imports(
        CORE_DIRECTORY, {"ui", "scripts"}
    )
    assert not violations, "\n".join(violations)
    
