import ast

import astor

from flaws.asttools import get_body_ast
from flaws.patterns import compile_template, match


def test_capture():
    @compile_template
    def useless_if(cond=ast.expr):
        if cond:
            return True
        else:
            return False

    @get_body_ast
    def tree():
        if x < 12:
            return True
        else:
            return False

    m = match(useless_if, tree)[0]
    assert astor.to_source(m.captures['cond']).strip() == '(x < 12)'


def test_more_captures():
    @compile_template
    def map_lambda(var=ast.Name, body=ast.expr, seq=ast.expr):
        map(lambda var: body, seq)

    @get_body_ast
    def tree():
        squares = map(lambda x: x ** 2, range(10))

    m = match(map_lambda, tree)[0]
    assert astor.to_source(m.captures['body']).strip() == '(x ** 2)'
    assert astor.to_source(m.captures['seq']).strip() == 'range(10)'
