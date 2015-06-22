import ast
import textwrap

from flaws.patterns import compile_template, match, get_body_ast


@compile_template
def useless_if():
    if ast.expr:
        return True
    else:
        return False


def test_exact():
    @get_body_ast
    def tree():
        if x < 12:
            return True
        else:
            return False
    assert match(useless_if, tree) == [tree[0]]


def test_irrelevant():
    @get_body_ast
    def tree():
        x = 1
    assert match(useless_if, tree) == []


def test_incomplete():
    @get_body_ast
    def tree():
        if y:
            return True
    assert match(useless_if, tree) == []


def test_offset():
    @get_body_ast
    def tree():
        y = 1
        if x < 12:
            return True
        else:
            return False
    assert match(useless_if, tree) == [tree[1]]


def test_nested():
    @get_body_ast
    def tree():
        while cond:
            if x < 12:
                return True
            else:
                return False
    assert match(useless_if, tree) == [tree[0].body[0]]


def test_constant_mismatch():
    @get_body_ast
    def tree():
        if x < 12:
            return False
        else:
            return False
    assert match(useless_if, tree) == []


def test_extra_statement():
    @get_body_ast
    def tree():
        if x < 12:
            return True
        else:
            return False
            pass
    assert match(useless_if, tree) == []
