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
        ast = parse_formula("$1.weight")
        assert isinstance(ast, ColumnRef)
        assert ast.column == 1
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
        ast = parse_formula("$1.a + $2.b * 3")
        assert isinstance(ast, BinOp)
        assert ast.op == "+"

    def test_empty_formula_raises(self):
        with pytest.raises(ParseError, match="Empty"):
            parse_formula("")

    def test_invalid_chars_raises(self):
        with pytest.raises(ParseError):
            parse_formula("1 @ 2")


class TestExtractReferences:
    def test_single_ref(self):
        ast = parse_formula("$1.slug")
        refs = extract_references(ast)
        assert refs == [(1, "slug")]

    def test_multiple_refs(self):
        ast = parse_formula("$1.a + $2.b")
        refs = extract_references(ast)
        assert (1, "a") in refs
        assert (2, "b") in refs

    def test_no_refs(self):
        ast = parse_formula("1 + 2")
        refs = extract_references(ast)
        assert refs == []


class TestEvaluate:
    def test_simple_addition(self):
        ast = parse_formula("$1.a + $2.b")
        result = evaluate(ast, {(1, "a"): 10.0, (2, "b"): 5.0})
        assert result == 15.0

    def test_multiplication(self):
        ast = parse_formula("$1.x * 2")
        result = evaluate(ast, {(1, "x"): 3.0})
        assert result == 6.0

    def test_none_propagation(self):
        ast = parse_formula("$1.a + $2.b")
        result = evaluate(ast, {(1, "a"): 10.0, (2, "b"): None})
        assert result is None

    def test_missing_ref_returns_none(self):
        ast = parse_formula("$1.missing")
        result = evaluate(ast, {})
        assert result is None

    def test_division_by_zero(self):
        ast = parse_formula("$1.a / $2.b")
        result = evaluate(ast, {(1, "a"): 10.0, (2, "b"): 0.0})
        assert result is None

    def test_unary_neg(self):
        ast = parse_formula("-$1.a")
        result = evaluate(ast, {(1, "a"): 5.0})
        assert result == -5.0

    def test_unary_neg_none(self):
        ast = parse_formula("-$1.a")
        result = evaluate(ast, {(1, "a"): None})
        assert result is None

    def test_complex_expression(self):
        ast = parse_formula("($1.a + $2.b) * 2")
        result = evaluate(ast, {(1, "a"): 3.0, (2, "b"): 7.0})
        assert result == 20.0

    def test_number_literal(self):
        ast = parse_formula("42")
        assert evaluate(ast, {}) == 42.0


class TestValidateFormula:
    def test_valid(self):
        assert validate_formula("$1.a + $2.b") == []

    def test_valid_number(self):
        assert validate_formula("42") == []

    def test_invalid(self):
        errors = validate_formula("")
        assert len(errors) > 0

    def test_invalid_chars(self):
        errors = validate_formula("1 @ 2")
        assert len(errors) > 0
