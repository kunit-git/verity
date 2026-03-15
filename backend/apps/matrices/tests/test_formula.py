"""Pure unit tests for the formula parser and evaluator — no DB needed."""
import pytest
from apps.matrices.formula import (
    BinOp,
    ColumnRef,
    Number,
    ParseError,
    UnaryNeg,
    evaluate,
    extract_references,
    parse_formula,
    validate_formula,
)


class TestParse:
    def test_number(self):
        ast = parse_formula("42")
        assert isinstance(ast, Number)
        assert ast.value == 42.0

    def test_decimal_number(self):
        ast = parse_formula("3.14")
        assert ast.value == 3.14

    def test_addition(self):
        ast = parse_formula("1 + 2")
        assert isinstance(ast, BinOp)
        assert ast.op == "+"

    def test_subtraction(self):
        ast = parse_formula("5 - 3")
        assert isinstance(ast, BinOp)
        assert ast.op == "-"

    def test_multiplication(self):
        ast = parse_formula("2 * 3")
        assert isinstance(ast, BinOp)
        assert ast.op == "*"

    def test_division(self):
        ast = parse_formula("6 / 2")
        assert isinstance(ast, BinOp)
        assert ast.op == "/"

    def test_column_ref(self):
        ast = parse_formula("$reqs.weight")
        assert isinstance(ast, ColumnRef)
        assert ast.source_name == "reqs"
        assert ast.field_slug == "weight"

    def test_nested_parens(self):
        ast = parse_formula("(1 + 2) * 3")
        assert isinstance(ast, BinOp)
        assert ast.op == "*"

    def test_unary_negation(self):
        ast = parse_formula("-5")
        assert isinstance(ast, UnaryNeg)
        assert isinstance(ast.operand, Number)

    def test_complex_expression(self):
        ast = parse_formula("$reqs.a + $tests.b * 3")
        assert isinstance(ast, BinOp)
        assert ast.op == "+"

    def test_empty_formula_raises(self):
        with pytest.raises(ParseError, match="Empty"):
            parse_formula("")

    def test_invalid_chars_raises(self):
        with pytest.raises(ParseError):
            parse_formula("1 @ 2")

    def test_hyphenated_source_name(self):
        ast = parse_formula("$req-status.value")
        assert isinstance(ast, ColumnRef)
        assert ast.source_name == "req-status"
        assert ast.field_slug == "value"


class TestExtractReferences:
    def test_single_ref(self):
        ast = parse_formula("$reqs.slug")
        refs = extract_references(ast)
        assert refs == [("reqs", "slug")]

    def test_multiple_refs(self):
        ast = parse_formula("$reqs.a + $tests.b")
        refs = extract_references(ast)
        assert ("reqs", "a") in refs
        assert ("tests", "b") in refs

    def test_no_refs(self):
        ast = parse_formula("1 + 2")
        refs = extract_references(ast)
        assert refs == []


class TestEvaluate:
    def test_simple_addition(self):
        ast = parse_formula("$reqs.a + $tests.b")
        result = evaluate(ast, {("reqs", "a"): 10.0, ("tests", "b"): 5.0})
        assert result == 15.0

    def test_multiplication(self):
        ast = parse_formula("$reqs.x * 2")
        result = evaluate(ast, {("reqs", "x"): 3.0})
        assert result == 6.0

    def test_none_propagation(self):
        ast = parse_formula("$reqs.a + $tests.b")
        result = evaluate(ast, {("reqs", "a"): 10.0, ("tests", "b"): None})
        assert result is None

    def test_missing_ref_returns_none(self):
        ast = parse_formula("$reqs.missing")
        result = evaluate(ast, {})
        assert result is None

    def test_division_by_zero(self):
        ast = parse_formula("$reqs.a / $tests.b")
        result = evaluate(ast, {("reqs", "a"): 10.0, ("tests", "b"): 0.0})
        assert result is None

    def test_unary_neg(self):
        ast = parse_formula("-$reqs.a")
        result = evaluate(ast, {("reqs", "a"): 5.0})
        assert result == -5.0

    def test_unary_neg_none(self):
        ast = parse_formula("-$reqs.a")
        result = evaluate(ast, {("reqs", "a"): None})
        assert result is None

    def test_complex_expression(self):
        ast = parse_formula("($reqs.a + $tests.b) * 2")
        result = evaluate(ast, {("reqs", "a"): 3.0, ("tests", "b"): 7.0})
        assert result == 20.0

    def test_number_literal(self):
        ast = parse_formula("42")
        assert evaluate(ast, {}) == 42.0


class TestValidateFormula:
    def test_valid(self):
        assert validate_formula("$reqs.a + $tests.b") == []

    def test_valid_number(self):
        assert validate_formula("42") == []

    def test_invalid(self):
        errors = validate_formula("")
        assert len(errors) > 0

    def test_invalid_chars(self):
        errors = validate_formula("1 @ 2")
        assert len(errors) > 0
