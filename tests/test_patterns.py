import ast
import textwrap

from flaws.patterns import compile_template, match, get_body_ast


@compile_template
def useless_if(cond=ast.expr):
    if cond:
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


# Multistatement template, vary names

@compile_template
def assignments():
    x = 1
    y = x


def test_multi():
    @get_body_ast
    def tree():
        x = 1
        y = x
    assert match(assignments, tree) == [tree[0]]


def test_partial():
    @get_body_ast
    def tree():
        x = 1
    assert match(assignments, tree) == []


def test_inner_partial():
    @get_body_ast
    def tree():
        x = 1
        f()
    assert match(assignments, tree) == []


def test_other_names():
    @get_body_ast
    def tree():
        a = 1
        b = a
    assert match(assignments, tree) == [tree[0]]


def test_name_clash():
    @get_body_ast
    def tree():
        a = 1
        a = a
    assert match(assignments, tree) == []


def test_name_mismatch():
    @get_body_ast
    def tree():
        a = 1
        b = c
    assert match(assignments, tree) == []


def test_subexpr():
    @compile_template
    def expr():
        x + 1

    @get_body_ast
    def tree():
        y = x + 1

    import astor

    assert match(expr, tree) == [tree[0].value]
