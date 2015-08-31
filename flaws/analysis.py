import ast
import os
import re
from collections import defaultdict

from funcy import cached_property, any

from .asttools import is_use, name_class
from .utils import slurp
from .scopes import fill_scopes


def global_usage(files):
    used = defaultdict(set)

    for package, pyfile in files.items():
        for name, nodes in pyfile.scope.names.items():
            if isinstance(nodes[0], ast.ImportFrom):
                module = get_module(nodes[0], pyfile.dotname)
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


def get_module(node, package):
    if not node.level:
        return node.module
    else:
        subs = package.split('.')
        subs = subs[:len(subs) - node.level]
        if node.module:
            subs.append(node.module)
        return '.'.join(subs)


# File utils

class FileSet(dict):
    def __init__(self, root, base=None):
        if base is None:
            base = root
        for filename in walk_files(root):
            pyfile = File(base, filename)
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
