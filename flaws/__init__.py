#!/usr/bin/env python
import sys
import ast

from funcy import all
import astor

from .asttools import (is_write, is_use, is_constant, is_param, is_import,
                       name_class, node_str, to_source)
from .scopes import TreeLinker, ScopeBuilder
from .infer import Inferer


def slurp(filename):
    with open(filename) as f:
        return f.read()


class MapLambda(object):
    def template(body=ast.expr, seq=ast.expr):
        map(lambda var: body, seq)

    def suggestion():
        [body for var in seq]

    # def template(cond=ast.expr):
    #     if cond:
    #         return True
    #     else:
    #         return False


def main():
    for filename in sys.argv[1:]:
        # print '> Analyzing %s...' % filename

        source = slurp(filename)
        tree = ast.parse(source, filename=filename)
        # print astor.dump(tree)

        # from .patterns import match, compile_template
        # template = compile_template(MapLambda.template)
        # print match(template, tree)

        TreeLinker().visit(tree)

        ScopeBuilder().visit(tree)
        # print tree.scope

        # print astor.dump(tree)
        # Inferer().visit(tree)

        # print to_source(tree)

        # for scope, name, nodes in top.walk():
        #     for node in nodes:
        #         print '%s = %s at %s' % (name, node.val, node_str(node))

        for scope, name, nodes in tree.scope.walk():
            node = nodes[0]
            if all(is_use, nodes) and not scope.is_global(name) and not scope.has_wildcards:
                print '%s:%d:%d: undefined variable %s' \
                      % (filename, node.lineno, node.col_offset, name)
            if not scope.is_class and all(is_write, nodes):
                if name == '_' or scope.is_module and re.search(r'^__\w+__$', name):
                    continue
                elif scope.exports is not None and name in scope.exports:
                    continue
                elif scope.exports is None and not name.startswith('_') and not is_import(node):
                    continue
                # TODO: check that it is method/classmethod
                elif is_param(node) and name in {'self', 'cls', 'kwargs', 'request'}:
                    continue
                print '%s:%d:%d: %s %s is never used' % \
                      (filename, node.lineno, node.col_offset, name_class(node), name)


if __name__ == '__main__':
    main()
