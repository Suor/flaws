#!/usr/bin/env python
import os
import sys
import ast
import re

from funcy import all, imapcat, split, map
import astor

from .asttools import (is_write, is_use, is_constant, is_param, is_import,
                       name_class, node_str, to_source)
from .scopes import fill_scopes
from .infer import Inferer
from .utils import slurp
from .analysis import global_usage, FileSet


import sys, ipdb, traceback

def info(type, value, tb):
    traceback.print_exception(type, value, tb)
    print
    ipdb.pm()

sys.excepthook = info


def main():
    kwargs, args = split(r'^--', sys.argv[1:])
    kwargs = dict(map(r'^--(\w+)=(.+)', kwargs))

    from .ext import django
    django.register(args, kwargs)

    files = FileSet(args, base=kwargs.get('base'), ignore=kwargs.get('ignore'))
    global_usage(files)
    return

    for package, pyfile in sorted(files.items()):
        # print '> Analyzing %s...' % filename

        # from .patterns import match, compile_template
        # template = compile_template(MapLambda.template)
        # print match(template, tree)

        # fill_scopes(tree)
        print pyfile.scope

        # print astor.dump(tree)
        # Inferer().visit(tree)

        # print to_source(tree)

        # for scope, name, nodes in top.walk():
        #     for node in nodes:
        #         print '%s = %s at %s' % (name, node.val, node_str(node))

        for scope, name, nodes in pyfile.scope.walk():
            node = nodes[0]
            if all(is_use, nodes) and not scope.is_global(name) and not scope.has_wildcards:
                print '%s:%d:%d: undefined variable %s' \
                      % (pyfile.filename, node.lineno, node.col_offset, name)
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
                      (pyfile.filename, node.lineno, node.col_offset, name_class(node), name)


if __name__ == '__main__':
    main()
