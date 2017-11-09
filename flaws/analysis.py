from __future__ import absolute_import
import ast
import os
import re
from collections import defaultdict

from funcy.py2 import cached_property, ikeep, any, all, remove
from tqdm import tqdm

from .asttools import is_write, is_use, is_param, is_import, name_class
from .utils import slurp
from .scopes import fill_scopes
from .ext import run_global_usage


IGNORED_VARS = {'__all__', '__file__', '__name__', '__version__', '__author__'}


def global_usage(files):
    used = defaultdict(set)
    # TODO: detect undefined names in a scope with star imports
    # # This is used to detect undefined names
    # starimports = defaultdict(set)
    # starimports[package].update(exports)

    # print files['cacheops'].scope

    # used[module][name] = [(mod1, node1), (mod2, node2), ...]
    # used[module, name] = [(mod1, node1), (mod2, node2), ...]
    # used[module][name] = (mod1, node1)
    # used[module, name] = (mod1, node1)

    # for package, pyfile in sorted(files.items()):
    for package, pyfile in tqdm(sorted(files.items()), leave=False):
        for scope in pyfile.scope.walk_scopes():
            for node in scope.imports:
                if isinstance(node, ast.ImportFrom):
                    module = get_import_module(node, pyfile, files)

                    # Mark all imported things as used
                    if module in files:
                        names = {alias.name for alias in node.names}
                        used[module].update(names)

                        # Handle star imports
                        if '*' in names:
                            exports = files[module].scope.exports
                            if exports is None:
                                print('%s:%d: star import with no __all__ in %s' % \
                                      (pyfile.filename, node.lineno, module))
                                exports = files[module].scope.implicit_exports

                            if pyfile.is_entry:
                                if pyfile.scope.exports:
                                    used[module].update(set(exports) & set(pyfile.scope.exports))
                                else:
                                    used[module].update(exports)
                            else:
                                used[module].update(
                                    name for name in exports
                                         if any(is_use, scope.maybe_from_star.get(name, ())))

                    # When importing module look for `module.name`
                    # TODO: support `from mod1 import mod2; mod2.mod3.func()`
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

        # Entry point usage
        if pyfile.is_entry:
            # TODO: warn about no __all__ in entry point?
            exports = pyfile.scope.exports or pyfile.scope.implicit_exports
            used[package].update(exports)

    run_global_usage(files, used)

    for package, pyfile in sorted(files.items()):
        for name, nodes in pyfile.scope.names.items():
            if name not in used[package] and name not in IGNORED_VARS:
                print('%s:%d: %s %s is never used (globally)' % \
                      (pyfile.filename, nodes[0].lineno, name_class(nodes[0]), name))


def find_attr(expr, node):
    parts = expr.split('.')[1:]
    i = 0
    while len(parts) > i and is_attr(node.up, parts[i]):
        node = node.up

    if isinstance(node.up, ast.Attribute):
        return node.up.attr

def is_attr(node, attr):
    return isinstance(node, ast.Attribute) and node.attr == attr


def get_import_module(node, pyfile, files):
    def _rel_import(module, level):
        subs = pyfile.dotname.split('.')[:-level]
        if module:
            subs.append(module)
        return '.'.join(subs)

    if not node.level:
        # Try relative import first
        # TODO: in python 3 it's always future
        if 'absolute_import' not in pyfile.scope.future:
            imported = _rel_import(node.module, 1)
            if imported in files:
                return imported
        return node.module
    else:
        return _rel_import(node.module, node.level)


def local_usage(files):
    for _, pyfile in sorted(files.items()):
        for scope, name, nodes in pyfile.scope.walk():
            node = nodes[0]
            if all(is_use, nodes) and not scope.is_global(name) and not scope.sees_stars:
                print('%s:%d:%d: undefined variable %s' \
                      % (pyfile.filename, node.lineno, node.col_offset, name))
            if not scope.is_class and all(is_write, nodes):
                if name == '_' or scope.is_module and re.search(r'^__\w+__$', name):
                    continue
                elif scope.exports is not None and name in scope.exports:
                    continue
                elif scope.exports is None and not name.startswith('_') and not is_import(node):
                    continue
                # NOTE: skipping all params for now as this gets too many false positives:
                #       protocols, overriden methods, signal handlers, etc.
                elif is_param(node):
                    continue
                # # TODO: check that it is method/classmethod
                # elif is_param(node) and name in {'self', 'cls', 'kwargs', 'request'}:
                #     continue
                # BUG: shows unused import when it's meant for reexport
                print('%s:%d:%d: %s %s is never used' % \
                      (pyfile.filename, node.lineno, node.col_offset, name_class(node), name))


# File utils

class FileSet(dict):
    def __init__(self, roots, base=None, ignore=None, entry_points=None):
        ignore_re = re.compile(ignore) if ignore else None
        entry_points = set((entry_points or '').split(','))

        for root in roots:
            if root.endswith('.py'):
                entry_point = root
                files = [root]
                root = os.path.dirname(root)
            else:
                entry_point = os.path.join(root, '__init__.py')
                if os.path.isfile(entry_point):
                    # Guess base
                    if base is None:
                        base = os.path.dirname(os.path.normpath(root))
                        if base == '':
                            base = '.'
                else:
                    entry_point = None

                files = walk_files(root)

            for filename in files:
                if ignore_re and ignore_re.search(filename):
                    continue
                pyfile = File(base or root, filename, entry_point == filename)
                self[pyfile.package] = pyfile
                if pyfile.package in entry_points:
                    pyfile.is_entry = True

    # def resolve_ref(self, module, name):
    #     pyfile = self[module]
    #     if name in pyfile.scope.names:
    #         return module, name
    #     else:
    #         # ...


class File(object):
    def __init__(self, base, filename, is_entry):
        self.base = base
        self.filename = filename
        self.is_entry = is_entry
        self.package, self.dotname = path_to_package(os.path.relpath(filename, base))

    def __str__(self):
        return '<File: %s>' % self.filename

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
