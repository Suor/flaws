#!/usr/bin/env python
import os
import sys
import ast
import re

from funcy import all, any, imapcat, cached_property
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


def walk_files(path, ext='.py'):
    for root, dirs, files in os.walk(path):
        for d in dirs:
            if d.startswith('.'):
                dirs.remove(d)
        for f in files:
            if f.endswith(ext):
                yield os.path.join(root, f)


def path_to_package(path):
    return re.sub('^\./|(.__init__)?\.py$', '', path).replace('/', '.')


class File(object):
    def __init__(self, base, filename):
        self.base = base
        self.filename = filename
        self.package = path_to_package(os.path.relpath(filename, base))

    @cached_property
    def tree(self):
        source = slurp(self.filename)
        return ast.parse(source, filename=self.filename)

    @cached_property
    def scope(self):
        TreeLinker().visit(self.tree)
        ScopeBuilder().visit(self.tree)
        return self.tree.scope


class FileSet(dict):
    def __init__(self, root, base=None):
        if base is None:
            base = root
        for filename in walk_files(root):
            pyfile = File(base, filename)
            self[pyfile.package] = pyfile


import sys, ipdb, traceback

def info(type, value, tb):
    traceback.print_exception(type, value, tb)
    print
    ipdb.pm()

sys.excepthook = info

from collections import defaultdict

def get_module(node, package):
    if not node.level:
        return node.module
    else:
        subs = package.split('.')
        subs = subs[:len(subs) - node.level]
        return '.'.join(subs + [node.module])

def main():
    used = defaultdict(set)
    files = FileSet(sys.argv[1], sys.argv[2] if len(sys.argv) >= 3 else None)
    for package, pyfile in files.items():
        for name, nodes in pyfile.scope.names.items():
            # if is_import(nodes[0]) and hasattr(nodes[0], 'module'):
            if isinstance(nodes[0], ast.ImportFrom):
                module = get_module(nodes[0], package)
                if module in files:
                    names = {alias.name for alias in nodes[0].names}
                    used[module].update(names)
            if any(is_use, nodes):
                used[package].add(name)

    for package, pyfile in sorted(files.items()):
        for name, nodes in pyfile.scope.names.items():
            if name not in used[package]:
                print '%s:%d:%d: %s %s is never used (globally)' % \
                      (pyfile.filename, nodes[0].lineno, nodes[0].col_offset, name_class(nodes[0]), name)


    from IPython import embed; embed()
    return

    for filename in imapcat(walk_files, sys.argv[1:]):
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
