"""
Safe formula evaluator for matrix formula columns.

Supports arithmetic (+, -, *, /, parentheses) and column references like $1.field-slug.
No eval(), no external deps.
"""

import re
from dataclasses import dataclass
from typing import Union


# ── AST Nodes ──


@dataclass
class Number:
    value: float


@dataclass
class ColumnRef:
    source_name: str  # name of the source to reference
    field_slug: str


@dataclass
class BinOp:
    op: str
    left: "ASTNode"
    right: "ASTNode"


@dataclass
class UnaryNeg:
    operand: "ASTNode"


ASTNode = Union[Number, ColumnRef, BinOp, UnaryNeg]


# ── Tokeniser ──

# Token patterns
_TOKEN_RE = re.compile(
    r"""
    \s*(?:
        (\d+(?:\.\d+)?)              # group 1: number
        |(\$([a-zA-Z][a-zA-Z0-9_-]*)\.([a-zA-Z0-9_-]+)) # group 2: full ref, 3: source name, 4: slug
        |([+\-*/()]) # group 5: operator / paren
    )\s*
    """,
    re.VERBOSE,
)


class ParseError(Exception):
    pass


def _tokenize(formula: str):
    pos = 0
    tokens = []
    for m in _TOKEN_RE.finditer(formula):
        if m.start() != pos:
            bad = formula[pos : m.start()].strip()
            if bad:
                raise ParseError(f"Unexpected characters: {bad!r}")
        if m.group(1) is not None:
            tokens.append(("NUM", float(m.group(1))))
        elif m.group(2) is not None:
            tokens.append(("REF", (m.group(3), m.group(4))))
        elif m.group(5) is not None:
            tokens.append(("OP", m.group(5)))
        pos = m.end()
    remaining = formula[pos:].strip()
    if remaining:
        raise ParseError(f"Unexpected characters at end: {remaining!r}")
    return tokens


# ── Recursive-descent parser ──


class _Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self):
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def consume(self, expected_type=None, expected_val=None):
        tok = self.peek()
        if tok is None:
            raise ParseError("Unexpected end of expression")
        if expected_type and tok[0] != expected_type:
            raise ParseError(f"Expected {expected_type}, got {tok}")
        if expected_val is not None and tok[1] != expected_val:
            raise ParseError(f"Expected {expected_val!r}, got {tok[1]!r}")
        self.pos += 1
        return tok

    def parse(self) -> ASTNode:
        node = self._expr()
        if self.pos < len(self.tokens):
            raise ParseError(f"Unexpected token: {self.tokens[self.pos]}")
        return node

    def _expr(self) -> ASTNode:
        node = self._term()
        while self.peek() and self.peek()[0] == "OP" and self.peek()[1] in ("+", "-"):
            op = self.consume()[1]
            right = self._term()
            node = BinOp(op, node, right)
        return node

    def _term(self) -> ASTNode:
        node = self._unary()
        while self.peek() and self.peek()[0] == "OP" and self.peek()[1] in ("*", "/"):
            op = self.consume()[1]
            right = self._unary()
            node = BinOp(op, node, right)
        return node

    def _unary(self) -> ASTNode:
        if self.peek() and self.peek() == ("OP", "-"):
            self.consume()
            operand = self._unary()
            return UnaryNeg(operand)
        return self._primary()

    def _primary(self) -> ASTNode:
        tok = self.peek()
        if tok is None:
            raise ParseError("Unexpected end of expression")
        if tok[0] == "NUM":
            self.consume()
            return Number(tok[1])
        if tok[0] == "REF":
            self.consume()
            source_name, slug = tok[1]
            return ColumnRef(source_name, slug)
        if tok == ("OP", "("):
            self.consume()
            node = self._expr()
            self.consume("OP", ")")
            return node
        raise ParseError(f"Unexpected token: {tok}")


# ── Public API ──


def parse_formula(formula: str) -> ASTNode:
    """Parse a formula string into an AST. Raises ParseError on invalid syntax."""
    tokens = _tokenize(formula)
    if not tokens:
        raise ParseError("Empty formula")
    return _Parser(tokens).parse()


def extract_references(node: ASTNode) -> list[tuple[str, str]]:
    """Return all (source_name, field_slug) pairs referenced in the AST."""
    refs = []

    def walk(n):
        if isinstance(n, ColumnRef):
            refs.append((n.source_name, n.field_slug))
        elif isinstance(n, BinOp):
            walk(n.left)
            walk(n.right)
        elif isinstance(n, UnaryNeg):
            walk(n.operand)

    walk(node)
    return refs


def evaluate(node: ASTNode, context: dict[tuple[str, str], float | None]) -> float | None:
    """
    Evaluate the AST given a context mapping (source_name, field_slug) → numeric value.
    Returns None if any referenced value is None or on division by zero.
    """
    if isinstance(node, Number):
        return node.value
    if isinstance(node, ColumnRef):
        val = context.get((node.source_name, node.field_slug))
        return val
    if isinstance(node, UnaryNeg):
        val = evaluate(node.operand, context)
        return -val if val is not None else None
    if isinstance(node, BinOp):
        left = evaluate(node.left, context)
        right = evaluate(node.right, context)
        if left is None or right is None:
            return None
        if node.op == "+":
            return left + right
        if node.op == "-":
            return left - right
        if node.op == "*":
            return left * right
        if node.op == "/":
            if right == 0:
                return None
            return left / right
    return None


def validate_formula(formula: str) -> list[str]:
    """Validate formula syntax. Returns list of error messages (empty = valid)."""
    try:
        parse_formula(formula)
        return []
    except ParseError as e:
        return [str(e)]
