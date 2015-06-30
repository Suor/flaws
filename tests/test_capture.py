import ast
import textwrap

import astor

from flaws.patterns import compile_template, match, get_body_ast


@compile_template
def useless_if(cond=ast.expr):
    if cond:
        return True
    else:
        return False


def test_capture():
    @get_body_ast
    def tree():
        if x < 12:
            return True
        else:
            return False

    m = match(useless_if, tree)[0]
    assert astor.to_source(m.captures['cond']) == '(x < 12)'
