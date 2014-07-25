import sys
import ast
from collections import defaultdict, deque

from funcy import *
from astpp import dump # use astor?


SOURCE = """
# import sys

x = 1
y = 2

def f(n):
    # global h
    return y * n * h

print x
"""

tree = ast.parse(SOURCE, filename='example.py')
print dump(tree)


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

    @property
    def is_module(self):
        return isinstance(self.node, ast.Module)

    @cached_property
    def module(self):
        scope = self
        while not scope.is_module:
            scope = scope.parent
        return scope

    def add(self, name, node):
        # Function defs and params are always in current scope.
        # Other names could be passed to parent scope upon exit, unless it's a module.
        if self.is_module                            \
                or isinstance(node, ast.FunctionDef) \
                or isinstance(node.ctx, ast.Param)   \
                or name in self.names:
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
            if self.is_module or any(isinstance(node.ctx, (ast.Store, ast.Del)) for node in nodes):
                self.names[name].extend(nodes)
                self.unscoped_names.pop(name)

    def dump(self, indent=''):
        name = self.node.__class__.__name__
        if hasattr(self.node, 'name'):
            name += ' ' + self.node.name
        if hasattr(self.node, 'lineno'):
            name += ' a line %d' % self.node.lineno

        title = indent + 'Scope ' + name
        names = '\n'.join(indent + '  %s = %s' % (name, nodes)
                          for name, nodes in sorted(self.names.items()))
        unscoped = '\n'.join(indent + '  unscoped %s = %s' % (name, nodes)
                             for name, nodes in sorted(self.unscoped_names.items()))
        children = ''.join(c.dump(indent + '  ') for c in self.children)

        return '\n'.join([title, names, unscoped, children])

    def __str__(self):
        return self.dump()


class ScopeBuilder(ast.NodeVisitor):
    def __init__(self):
        self.scopes = deque()

    # Scope mechanics
    @property
    def scope(self):
        if self.scopes:
            return self.scopes[-1]
        else:
            return None

    def push_scope(self, node):
        self.scopes.append(Scope(self.scope, node))

    def pop_scope(self):
        current = self.scope
        current.resolve()
        self.scopes.pop()
        if self.scope:
            self.scope.unscoped_names = current.unscoped_names
            current.unscoped_names = {}
        return current

    # Visiting
    def visit_Module(self, node):
        self.push_scope(node)
        self.generic_visit(node)
        return self.pop_scope()

    def visit_Class(self, node):
        raise NotImplementedError

    def visit_FunctionDef(self, node):
        print 'visit_FunctionDef'
        self.scope.add(node.name, node)

        self.push_scope(node)
        self.generic_visit(node)
        print 'exit visit_FunctionDef'
        return self.pop_scope()

    def visit_Name(self, node):
        print 'Name', node.id, node.ctx
        self.scope.add(node.id, node)

    def visit_Global(self, node):
        self.scope.make_global(node.names)


sb = ScopeBuilder()
scope = sb.visit(tree)
print scope
