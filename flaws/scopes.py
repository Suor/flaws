import ast
from collections import defaultdict, deque

from funcy.py2 import cached_property, any, icat, iterate, takewhile, ikeep, remove
from funcy.py3 import lsplit_by

from .asttools import nodes_str, is_write, is_read, is_param, ast_eval


# TODO: distinguish python versions
try:
    import builtins
except ImportError:
    import __builtin__ as builtins
BUILTINS = set(dir(builtins))
GLOBALS = BUILTINS | {'__name__', '__file__'}


class Scope(object):
    def __init__(self, parent, node):
        self.parent = parent
        if parent:
            parent.children.append(self)
        self.children = []

        self.node = node
        self.names = defaultdict(list)
        self.unscoped_names = defaultdict(list)
        self.global_names = set()
        self.imports = []
        self.has_stars = False
        self.maybe_from_star = defaultdict(list)
        self.future = set()

    def freeze(self):
        """
        Prevent accidental subsequent changes.
        Helps with debugging analysis.
        """
        assert self.is_module

        for scope in self.walk_scopes():
            # frozendict would be even better
            _freeze = lambda d: {name: tuple(nodes) for name, nodes in d.items()}
            scope.names = _freeze(scope.names)
            scope.maybe_from_star = _freeze(scope.maybe_from_star)

            self.imports = tuple(self.imports)
            self.future = frozenset(self.future)

            # Clean unscoped names
            assert not scope.unscoped_names
            del scope.unscoped_names
            del scope.global_names

    @cached_property
    def module(self):
        scope = self
        while not scope.is_module:
            scope = scope.parent
        return scope

    @property
    def is_module(self):
        return isinstance(self.node, ast.Module)

    @property
    def is_class(self):
        return isinstance(self.node, ast.ClassDef)

    @property
    def sees_stars(self):
        parents = takewhile(bool, iterate(lambda s: s.parent, self))
        return any(s.has_stars for s in parents)

    @cached_property
    def exports(self):
        # There are several possible scenarious:
        #   1. Explicit exports
        #   2. No explicit exports, using _ prefix?
        #   3. Failed to parse __all__
        #   4. Not a module - same as __all__ = []?
        # We treat 3 as 2 for now.
        if not self.is_module:
            return []
        if '__all__' not in self.names:
            return None

        exports_node = self.names['__all__'][0]
        assign = exports_node.up
        if not isinstance(assign, ast.Assign) or len(assign.targets) != 1:
            print("WARN: failed parsing __all__")
            return None

        try:
            return ast_eval(assign.value)
        except ValueError:
            print("WARN: failed parsing __all__")
            return None

    @property
    def implicit_exports(self):
        assert self.is_module
        return remove(r'^_', self.names)

    # Names

    def add(self, name, node):
        # Params are always in current scope.
        # Other names could be made global or passed to parent scope upon exit,
        # unless we are in a module.
        if name in self.names or self.is_module or is_param(node):
            self.names[name].append(node)
        else:
            self.unscoped_names[name].append(node)

    def make_global(self, names):
        self.global_names.update(names)

    def resolve(self):
        # Extract global names to module scope
        for name in self.global_names:
            nodes = self.unscoped_names.pop(name, [])
            self.module.names[name].extend(nodes)

        # TODO: add nonlocal support here

        # Detect local names
        for name, nodes in list(self.unscoped_names.items()):
            # Class scope special semantics: reads before first write go out
            if self.is_class:
                starting_reads, rest = lsplit_by(is_read, nodes)
                if rest:
                    self.names[name].extend(rest)
                    self.unscoped_names[name] = starting_reads
            elif self.is_module or any(is_write, nodes):
                self.names[name].extend(nodes)
                self.unscoped_names.pop(name)

        # Resolve nested
        if not self.is_class:
            for scope in self.walk_scopes():
                self._resolve_unscoped(scope)

    def _resolve_unscoped(self, from_scope):
        for name, nodes in list(from_scope.unscoped_names.items()):
            # NOTE: star import in nested scope may break a chain,
            #       no way to know locally
            if self.has_stars:
                self.maybe_from_star[name] = nodes

            # If name is known or known global then own it
            if name in self.names or self.is_global(name):
                self.names[name].extend(nodes)
                from_scope.unscoped_names.pop(name)
            # If reached top level leave all unscoped inplace
            elif self.is_module:
                from_scope.names[name].extend(nodes)
                from_scope.unscoped_names.pop(name)

    def walk_scopes(self):
        yield self
        for child in self.children:
            for scope in child.walk_scopes():
                yield scope

    def walk(self):
        for name, nodes in self.names.items():
            yield self, name, nodes

        for child in self.children:
            for scope, name, nodes in child.walk():
                yield scope, name, nodes

    def is_global(self, name):
        return self.is_module and name in GLOBALS

    # Stringification

    def dump(self, indent=''):
        name = self.node.__class__.__name__
        if hasattr(self.node, 'name'):
            name += ' ' + self.node.name
        if hasattr(self.node, 'lineno'):
            name += ' at line %d' % self.node.lineno

        title = indent + 'Scope ' + name
        names = '\n'.join(indent + '  %s = %s' % (name, nodes_str(nodes))
                          for name, nodes in sorted(self.names.items()))
        if hasattr(self, 'unscoped_names'):
            unscoped = '\n'.join(indent + '  unscoped %s = %s' % (name, nodes_str(nodes))
                                 for name, nodes in sorted(self.unscoped_names.items()))
        else:
            unscoped = None
        children = '\n'.join('\n' + c.dump(indent + '  ') for c in self.children)

        return '\n'.join(ikeep([title, names, unscoped, children]))

    def __str__(self):
        return self.dump()


class TreeLinker(ast.NodeVisitor):
    def __init__(self):
        self.stack = deque()

    def visit(self, node):
        if self.stack:
            node.up = self.stack[-1]
        self.stack.append(node)
        self.generic_visit(node)
        self.stack.pop()


class ScopeBuilder(ast.NodeVisitor):
    def __init__(self):
        self.scopes = deque()

    def visit_all(self, *node_lists):
        for node in icat(node_lists):
            self.visit(node)

    # Scope mechanics
    @property
    def scope(self):
        if self.scopes:
            return self.scopes[-1]
        else:
            return None

    def push_scope(self, node):
        node.scope = Scope(self.scope, node)
        self.scopes.append(node.scope)

    def pop_scope(self):
        self.scope.resolve()
        self.scopes.pop()

    # Visiting
    def visit_Module(self, node):
        self.push_scope(node)
        self.generic_visit(node)
        self.pop_scope()

    def visit_Import(self, node):
        self.scope.imports.append(node)

        for alias in node.names:
            name = alias.asname or alias.name
            if name == '*':
                self.scope.has_stars = True
            else:
                name = name.split('.')[0]
                self.scope.add(name, node)

    def visit_ImportFrom(self, node):
        if node.module == '__future__':
            self.scope.future.update(alias.name for alias in node.names)
        else:
            self.visit_Import(node)

    def visit_ClassDef(self, node):
        self.scope.add(node.name, node)
        # TODO: handle python 3 style metaclass
        self.visit_all(node.decorator_list, node.bases)

        self.push_scope(node)
        self.visit_all(node.body)
        self.pop_scope()

    def visit_FunctionDef(self, node):
        self.scope.add(node.name, node)
        self.visit_all(node.decorator_list, node.args.defaults)

        self.push_scope(node)
        self.visit_all(node.args.args, node.body)
        # Visit vararg and kwarg
        # NOTE: arguments node doesn't have lineno and col_offset,
        #       so we copy them from a function node
        node.args.lineno = node.lineno
        node.args.col_offset = node.col_offset
        if node.args.vararg:
            self.scope.add(node.args.vararg, node.args)
        if node.args.kwarg:
            self.scope.add(node.args.kwarg, node.args)
        # TODO: handle kwonlyargs
        self.pop_scope()

    def visit_Lambda(self, node):
        self.push_scope(node)
        self.visit_all(node.args.args)
        # Visit vararg and kwarg
        # NOTE: arguments node doesn't have lineno and col_offset,
        #       so we copy them from a function node
        node.args.lineno = node.lineno
        node.args.col_offset = node.col_offset
        if node.args.vararg:
            self.scope.add(node.args.vararg, node.args)
        if node.args.kwarg:
            self.scope.add(node.args.kwarg, node.args)
        # TODO: handle kwonlyargs
        self.visit(node.body)
        self.pop_scope()

    def visit_Assign(self, node):
        # Visit expression first to get outer reads in class scope
        self.visit(node.value)
        self.visit_all(node.targets)

    def visit_Name(self, node):
        # TODO: respect assignments to these or make it a separate error
        self.scope.add(node.id, node)

    def visit_arg(self, node):
        self.scope.add(node.arg, node)

    def visit_Global(self, node):
        self.scope.make_global(node.names)


def fill_scopes(tree):
    TreeLinker().visit(tree)
    ScopeBuilder().visit(tree)
    tree.scope.freeze()
