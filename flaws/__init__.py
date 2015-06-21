#!/usr/bin/env python
import sys
import ast

from funcy import all
from astpp import dump # use astor?

from .scopes import TreeLinker, ScopeBuilder
from .asttools import is_write, is_use, is_constant, name_class


def slurp(filename):
    with open(filename) as f:
        return f.read()


def main():
    for filename in sys.argv[1:]:
        print '> Analyzing %s...' % filename

        source = slurp(filename)
        tree = ast.parse(source, filename=filename)
        # print dump(tree)

        TreeLinker().visit(tree)

        sb = ScopeBuilder()
        top = sb.visit(tree)
        # print top

        for scope, name, nodes in top.walk():
            node = nodes[0]
            if all(is_use, nodes):
                print 'Undefined variable %s at %s:%d:%d' % (name, filename, node.lineno, node.col_offset)
            if not scope.is_class and all(is_write, nodes):
                if name == '__all__' and scope.is_module:
                    continue
                elif scope.exports is not None and name in scope.exports:
                    continue
                elif scope.exports is None and not name.startswith('_'):
                    if isinstance(node, (ast.FunctionDef, ast.ClassDef)) or is_constant(node):
                        continue
                print '%s %s is never used at %s:%d:%d' % \
                      (name_class(node).title(), name, filename, node.lineno, node.col_offset)


if __name__ == '__main__':
    main()
