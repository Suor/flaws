#!/usr/bin/env python
import sys
import ast

from funcy import all
import astor

from .asttools import is_write, is_use, is_constant, name_class, node_str, to_source
from .scopes import TreeLinker, ScopeBuilder
from .infer import Inferer


def slurp(filename):
    with open(filename) as f:
        return f.read()


def main():
    for filename in sys.argv[1:]:
        print '> Analyzing %s...' % filename

        source = slurp(filename)
        tree = ast.parse(source, filename=filename)
        # print astor.dump(tree)

        TreeLinker().visit(tree)

        ScopeBuilder().visit(tree)
        print tree.scope

        print astor.dump(tree)
        Inferer().visit(tree)

        print to_source(tree)

        # for scope, name, nodes in top.walk():
        #     for node in nodes:
        #         print '%s = %s at %s' % (name, node.val, node_str(node))

        for scope, name, nodes in tree.scope.walk():
            node = nodes[0]
            if all(is_use, nodes) and not scope.is_builtin(name):
                print 'Undefined variable %s at %s:%d:%d' \
                      % (name, filename, node.lineno, node.col_offset)
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
