
"""Architecture boundary tests for TradeLab Pro."""

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIRECTORY = PROJECT_ROOT / "data"


def test_data_layer_does_not_import_scripts():
    """
    The data layer must not depend on maintenance scripts.

    Reusable business and validation logic belongs in data/
    or core/, not inside scripts/.
    """
    violations = []

    for python_file in DATA_DIRECTORY.rglob("*.py"):
        source = python_file.read_text(encoding="utf-8")
        syntax_tree = ast.parse(source, filename=str(python_file))

        for node in ast.walk(syntax_tree):
            imported_module = None

            if isinstance(node, ast.ImportFrom):
                imported_module = node.module

            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "scripts" or alias.name.startswith(
                        "scripts."
                    ):
                        violations.append(
                            f"{python_file.relative_to(PROJECT_ROOT)}:"
                            f"{node.lineno} imports {alias.name}"
                        )

            if (
                imported_module == "scripts"
                or (
                    imported_module
                    and imported_module.startswith("scripts.")
                )
            ):
                violations.append(
                    f"{python_file.relative_to(PROJECT_ROOT)}:"
                    f"{node.lineno} imports {imported_module}"
                )

    assert not violations, (
        "Data layer must not import from scripts/. "
        "Move reusable logic into data/ or core/:\n"
        + "\n".join(violations)
    )
  
