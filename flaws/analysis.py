import ast
import os
import re
from collections import defaultdict

from funcy import cached_property, any, imapcat, isa, ikeep, first, all, imapcat, split, map
from tqdm import tqdm

from .asttools import (is_write, is_use, is_constant, is_param, is_import, is_name,
                       name_class, node_str, to_source)
from .utils import slurp
from .scopes import fill_scopes
from .ext import run_global_usage


IGNORED_VARS = {'__all__', '__file__', '__name__', '__version__'}


def global_usage(files):
    used = defaultdict(set)

    for package, pyfile in tqdm(sorted(files.items())):
        # TODO: cycle imports explicitely
        for name, nodes in pyfile.scope.names.items():
            # Symbol imports
            if isinstance(nodes[0], ast.ImportFrom):
                module = get_module(nodes[0], pyfile.dotname)
                if module in files:
                    names = {alias.name for alias in nodes[0].names}
                    used[module].update(names)
                # TODO: check if asname should be used here
                # TODO: support `from mod1 import mod2; mod2.mod3.func()`
                full_name = '%s.%s' % (module, name)
                if full_name in files:
                    for node in nodes[1:]:
                        if isinstance(node, ast.Name) and isinstance(node.up, ast.Attribute):
                            used[full_name].add(node.up.attr)
            # Module imports
            elif isinstance(nodes[0], ast.Import):
                # TODO: support compound imports
                alias = first(a for a in nodes[0].names if a.name.startswith(name) or a.asname == name)

                if alias.name in files:
                    attrs = ikeep(find_attr(alias.asname or alias.name, node) for node in nodes[1:])
                    used[alias.name].update(attrs)

            # Direct usage
            if any(is_use, nodes):
                used[package].add(name)

    run_global_usage(files, used)

    for package, pyfile in sorted(files.items()):
        for name, nodes in pyfile.scope.names.items():
            if name not in used[package] and name not in IGNORED_VARS:
                print '%s:%d:%d: %s %s is never used (globally)' % \
                      (pyfile.filename, nodes[0].lineno, nodes[0].col_offset, name_class(nodes[0]), name)


def find_attr(expr, node):
    parts = expr.split('.')[1:]
    i = 0
    while len(parts) > i and is_attr(node.up, parts[i]):
        node = node.up

    if isinstance(node.up, ast.Attribute):
        return node.up.attr

def is_attr(node, attr):
    return isinstance(node, ast.Attribute) and node.attr == attr


def get_module(node, package):
    if not node.level:
        return node.module
    else:
        subs = package.split('.')
        subs = subs[:len(subs) - node.level]
        if node.module:
            subs.append(node.module)
        return '.'.join(subs)


def local_usage(files):
    for package, pyfile in sorted(files.items()):
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


# File utils

class FileSet(dict):
    def __init__(self, roots, base=None, ignore=None):
        ignore_re = re.compile(ignore) if ignore else None

        for root in roots:
            if root.endswith('.py'):
                files = [root]
                root = os.path.dirname(root)
            else:
                files = walk_files(root)
            for filename in files:
                if ignore_re and ignore_re.search(filename):
                    continue
                pyfile = File(base or root, filename)
                self[pyfile.package] = pyfile


class File(object):
    def __init__(self, base, filename):
        self.base = base
        self.filename = filename
        self.package, self.dotname = path_to_package(os.path.relpath(filename, base))

    @cached_property
    def tree(self):
        source = slurp(self.filename)
        return ast.parse(source, filename=self.filename)


    @cached_property
    def scope(self):
        fill_scopes(self.tree)
        return self.tree.scope


def walk_files(path, ext='.py'):
    for root, dirs, files in os.walk(path):
        for d in dirs:
            if d.startswith('.'):
                dirs.remove(d)
        for f in files:
            if f.endswith(ext):
                yield os.path.join(root, f)


def path_to_package(path):
    dotname = re.sub(r'^\./|\.py$', '', path).replace('/', '.')
    package = re.sub(r'\.__init__$', '', dotname)
    return package, dotname
