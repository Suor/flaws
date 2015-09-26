import ast
from collections import defaultdict, deque

from funcy import cached_property, any, icat, iterate, takewhile

from .asttools import nodes_str, is_write, ast_eval


# TODO: distinguish python versions
import __builtin__
BUILTINS = set(dir(__builtin__))
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
        self.wildcards = []

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
    def has_wildcards(self):
        parents = takewhile(bool, iterate(lambda s: s.parent, self))
        return any(s.wildcards for s in parents)

    # @print_exits
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
            print "WARN: failed parsing __all__"
            return None

        try:
            return ast_eval(assign.value)
        except ValueError:
            print "WARN: failed parsing __all__"
            return None

    # Names

    def add(self, name, node):
        # Params are always in current scope.
        # Other names could be made global or passed to parent scope upon exit,
        # unless we are in a module.
        is_param = isinstance(node, ast.Name) and isinstance(node.ctx, ast.Param)
        if is_param or name in self.names or self.is_module:
            self.names[name].append(node)
        else:
            self.unscoped_names[name].append(node)
        node.in_scope = self

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
            if self.is_module or any(is_write, nodes):
                self.names[name].extend(nodes)
                self.unscoped_names.pop(name)

        # Resolve nested
        if not self.is_class:
            for scope in self.walk_scopes():
                self._resolve_unscoped(scope)

    def _resolve_unscoped(self, from_scope):
        for name, nodes in list(from_scope.unscoped_names.items()):
            if name in self.names or self.is_global(name):
                self.names[name].extend(nodes)
                from_scope.unscoped_names.pop(name)
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
            name += ' a line %d' % self.node.lineno

        title = indent + 'Scope ' + name
        names = '\n'.join(indent + '  %s = %s' % (name, nodes_str(nodes))
                          for name, nodes in sorted(self.names.items()))
        unscoped = '\n'.join(indent + '  unscoped %s = %s' % (name, nodes_str(nodes))
                             for name, nodes in sorted(self.unscoped_names.items()))
        children = ''.join(c.dump(indent + '  ') for c in self.children)

        return '\n'.join([title, names, unscoped, children])

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
        for alias in node.names:
            name = alias.asname or alias.name
            if name == '*':
                if not self.scope.is_module:
                    print 'WARN: wildcard import in nested scope'
                self.scope.wildcards.append(node)
            else:
                name = name.split('.')[0]
                self.scope.add(name, node)

    def visit_ImportFrom(self, node):
        if node.module != '__future__':
            self.visit_Import(node)

    def visit_ClassDef(self, node):
        self.scope.add(node.name, node)
        # TODO: handle python 3 style metaclass
        self.visit_all(node.decorator_list, node.bases)

        self.push_scope(node)
        self.visit_all(node.body)
        self.pop_scope()

    def visit_FunctionDef(self, node):
        # print 'visit_FunctionDef'
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
        # print 'exit visit_FunctionDef', self.scope.unscoped_names
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

    def visit_Name(self, node):
        # print 'Name', node.id, node.ctx
        # TODO: respect assignments to these or make it a separate error
        self.scope.add(node.id, node)

    def visit_Global(self, node):
        self.scope.make_global(node.names)


def fill_scopes(tree):
    TreeLinker().visit(tree)
    ScopeBuilder().visit(tree)
