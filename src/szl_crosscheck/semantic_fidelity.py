"""Source-anchored finite-domain equivalence for restricted position-puzzle clues.

Checks the meanings of two encodings against a separately provided canonical
expression for the exact published wording. This is NOT a language translator,
a uniqueness proof, or an independent attestation of the source expression.
"""
from __future__ import annotations

import ast
import itertools
from collections.abc import Mapping

MAX_HOUSES = 6
MAX_REFERENCES = 5


class SemanticInputError(ValueError):
    """Unsupported input or exhausted finite-domain validation bounds."""


def _parse(expr: str, categories: Mapping[str, str]) -> tuple[ast.AST, set[str]]:
    if not isinstance(expr, str) or len(expr) > 2000:
        raise SemanticInputError("expression must be a bounded string")
    try:
        tree = ast.parse(expr, mode="eval")
    except (SyntaxError, ValueError) as exc:
        raise SemanticInputError("invalid expression") from exc
    referenced: set[str] = set()

    def validate(node: ast.AST) -> None:
        if isinstance(node, ast.Expression):
            validate(node.body)
        elif isinstance(node, ast.Constant) and type(node.value) is int:
            if abs(node.value) > 100:
                raise SemanticInputError("integer out of range")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
            name = node.func.id
            if name == "pos" and len(node.args) == 1 and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                value = node.args[0].value.strip().lower()
                if value not in categories:
                    raise SemanticInputError("unrecognized position value")
                referenced.add(value)
            elif name in {"Abs", "Not"} and len(node.args) == 1:
                validate(node.args[0])
            elif name == "Implies" and len(node.args) == 2:
                for arg in node.args:
                    validate(arg)
            elif name in {"And", "Or"} and 1 <= len(node.args) <= 8:
                for arg in node.args:
                    validate(arg)
            else:
                raise SemanticInputError("unsupported call")
        elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub)):
            validate(node.left)
            validate(node.right)
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            validate(node.operand)
        elif isinstance(node, ast.Compare) and len(node.ops) == 1 and isinstance(node.ops[0], (ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE)):
            validate(node.left)
            validate(node.comparators[0])
        else:
            raise SemanticInputError("unsupported expression syntax")

    validate(tree)
    return tree.body, referenced


def _evaluate(node: ast.AST, assignment: Mapping[str, int]):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Call):
        name = node.func.id
        if name == "pos":
            return assignment[node.args[0].value.strip().lower()]
        args = [_evaluate(arg, assignment) for arg in node.args]
        if name == "Abs":
            return abs(args[0])
        if name == "Not":
            return not bool(args[0])
        if name == "And":
            return all(map(bool, args))
        if name == "Or":
            return any(map(bool, args))
        if name == "Implies":
            return not bool(args[0]) or bool(args[1])
    if isinstance(node, ast.BinOp):
        a, b = _evaluate(node.left, assignment), _evaluate(node.right, assignment)
        return a + b if isinstance(node.op, ast.Add) else a - b
    if isinstance(node, ast.UnaryOp):
        a = _evaluate(node.operand, assignment)
        return -a if isinstance(node.op, ast.USub) else +a
    if isinstance(node, ast.Compare):
        a, b = _evaluate(node.left, assignment), _evaluate(node.comparators[0], assignment)
        op = node.ops[0]
        if isinstance(op, ast.Eq):
            return a == b
        if isinstance(op, ast.NotEq):
            return a != b
        if isinstance(op, ast.Lt):
            return a < b
        if isinstance(op, ast.LtE):
            return a <= b
        if isinstance(op, ast.Gt):
            return a > b
        return a >= b
    raise SemanticInputError("unsupported expression")


def compare_position_clue(*, houses: int, categories: Mapping[str, str], source: str | None,
                          encoder_a: str, encoder_b: str) -> dict:
    """Check finite semantics with all-different values inside each category.

    source must be independently reviewed for the EXACT published clue wording;
    two encoders agreeing cannot establish that authority.
    """
    if type(houses) is not int or not 2 <= houses <= MAX_HOUSES:
        raise SemanticInputError("house count out of supported range")
    if not isinstance(categories, Mapping) or not categories:
        raise SemanticInputError("nonempty category map required")
    normalized = {}
    for name, group in categories.items():
        if not isinstance(name, str) or not name.strip() or not isinstance(group, str) or not group.strip():
            raise SemanticInputError("invalid category entry")
        key = name.strip().lower()
        if key in normalized:
            raise SemanticInputError("duplicate category value")
        normalized[key] = group.strip().lower()
    parsed = {}
    refs = set()
    for label, expr in (("a", encoder_a), ("b", encoder_b), ("source", source)):
        if expr is None and label == "source":
            continue
        parsed[label], names = _parse(expr, normalized)
        refs.update(names)
    if len(refs) > MAX_REFERENCES:
        raise SemanticInputError("too many referenced values for exhaustive check")
    names = sorted(refs)
    comparisons = [("a", "b")]
    if "source" in parsed:
        comparisons.extend((("a", "source"), ("b", "source")))
    witnesses = {}
    checked = 0
    for values in itertools.product(range(1, houses + 1), repeat=len(names)):
        assigned = dict(zip(names, values))
        if any(assigned[x] == assigned[y] for i, x in enumerate(names)
               for y in names[i + 1:] if normalized[x] == normalized[y]):
            continue
        checked += 1
        outcomes = {label: bool(_evaluate(node, assigned)) for label, node in parsed.items()}
        for left, right in comparisons:
            if outcomes[left] != outcomes[right] and f"{left}_vs_{right}" not in witnesses:
                witnesses[f"{left}_vs_{right}"] = {"assignment": assigned, "values": outcomes}
    if checked == 0:
        raise SemanticInputError("base domain has no valid assignments")
    status = "INDETERMINATE" if "source" not in parsed else "DRIFT" if witnesses else "MATCH"
    return {"schema": "szl.semantic-fidelity.v1", "status": status,
            "source_bound": "source" in parsed, "checked_assignments": checked,
            "dual_equivalent": "a_vs_b" not in witnesses,
            "source_equivalent": None if "source" not in parsed else not any(
                k.endswith("_vs_source") for k in witnesses),
            "witnesses": witnesses, "uniqueness_certified": False,
            "execution_authorized": False,
            "limit": "Finite position DSL only; equivalence to supplied reference, not natural-language truth"}
