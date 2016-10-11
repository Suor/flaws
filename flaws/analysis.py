from __future__ import absolute_import
import ast
import os
import re
from collections import defaultdict

from funcy import cached_property, ikeep, any, all, remove
from tqdm import tqdm

from .asttools import is_write, is_use, is_param, is_import, name_class
from .utils import slurp
from .scopes import fill_scopes
from .ext import run_global_usage


IGNORED_VARS = {'__all__', '__file__', '__name__', '__version__'}


def global_usage(files):
    used = defaultdict(set)

    for package, pyfile in tqdm(sorted(files.items())):
        for scope in pyfile.scope.walk_scopes():
            for node in scope.imports:
                if isinstance(node, ast.ImportFrom):
                    module = get_import_module(node, pyfile.dotname)

                    # Mark all imported things as used
                    if module in files:
                        names = {alias.name for alias in node.names}
                        used[module].update(names)

                    # When importing module look for `module.name`
                    # TODO: support `from mod1 import mod2; mod2.mod3.func()`
                    # TODO: handle star imports
                    for alias in node.names:
                        full_name = '%s.%s' % (module, alias.name)
                        if full_name in files:
                            nodes = scope.names[alias.asname or alias.name]
                            used[full_name].update(
                                n.up.attr for n in nodes if isinstance(n.up, ast.Attribute))

                elif isinstance(node, ast.Import):
                    # TODO: support `import mod1; mod1.mod2.func()`
                    # TODO: handle non-future relative imports
                    for alias in node.names:
                        if alias.name in files:
                            nodes = scope.names[(alias.asname or alias.name).split('.')[0]]
                            attrs = ikeep(find_attr(alias.asname or alias.name, node)
                                          for node in nodes[1:])
                            used[alias.name].update(attrs)

        # Direct usage
        for name, nodes in pyfile.scope.names.items():
            if any(is_use, nodes):
                used[package].add(name)

    run_global_usage(files, used)

    for package, pyfile in sorted(files.items()):
        for name, nodes in pyfile.scope.names.items():
            if name not in used[package] and name not in IGNORED_VARS:
                print '%s:%d: %s %s is never used (globally)' % \
                      (pyfile.filename, nodes[0].lineno, name_class(nodes[0]), name)


def find_attr(expr, node):
    parts = expr.split('.')[1:]
    i = 0
    while len(parts) > i and is_attr(node.up, parts[i]):
        node = node.up

    if isinstance(node.up, ast.Attribute):
        return node.up.attr

def is_attr(node, attr):
    return isinstance(node, ast.Attribute) and node.attr == attr


def get_import_module(node, package):
    if not node.level:
        return node.module
    else:
        subs = package.split('.')
        subs = subs[:len(subs) - node.level]
        if node.module:
            subs.append(node.module)
        return '.'.join(subs)


def local_usage(files):
    for _, pyfile in sorted(files.items()):
        for scope, name, nodes in pyfile.scope.walk():
            node = nodes[0]
            if all(is_use, nodes) and not scope.is_global(name) and not scope.sees_wildcards:
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

            # Guess base
            if base is None and os.path.isfile(os.path.join(root, '__init__.py')):
                root = os.path.dirname(os.path.normpath(root))

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
