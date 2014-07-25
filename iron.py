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
    global h
    return y * n

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

        # return some(_.is_module, iterate(_.parent, self))
        # return some(attrgetter('is_module'), iterate(attrgetter('parent'), self))

    def add(self, name, node):
        # load/store context is in the node
        if isinstance(node.ctx, ast.Param) or name in self.names:
            self.names[name].append(node)
        else:
            self.unscoped_names.append(node)

    def make_global(self, names):
        self.global_names.update(names)

    def resolve(self):
        # Extract global names to module scope
        for name in self.global_names:
            nodes = self.unscoped_names.pop(name, [])
            self.module.nodes[name].extend(nodes)

        # TODO: add nonlocal support here

        # Detect local names
        for name, nodes in self.unscoped_names.items():
            if any(isa(ast.Store, ast.Del, ast.Param), nodes):
                self.scope.add(name, *nodes)
                # ...

    # def __contains__(self, name):
    #     return name in self.names

    def dump(self, indent=''):
        name = self.node.__class__.__name__
        if hasattr(self.node, 'name'):
            name += ' ' + self.node.name
        if hasattr(self.node, 'lineno'):
            name += ' a line %d' % self.node.lineno

        title = indent + 'Scope ' + name
        names = '\n'.join(indent + '  %s = %s' % (name, nodes)
                          for name, nodes in sorted(self.names.items()))
        children = ''.join(c.dump(indent + '  ') for c in self.children)

        return title + '\n' + names + '\n' + children

    def __str__(self):
        return self.dump()

# class ScopedName(object):
#     def __init__(self, name, scope):
#         self.name = name
#         self.scope = scope
#         self.context = None
#         self.nodes = []


class ScopeBuilder(ast.NodeVisitor):
    def __init__(self):
        self.scopes = deque()
        self.global_names = set()
        self.unscoped_names = defaultdict(list)

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
        from funcy import first, any, isa

        # Extract global names to module scope
        if self.global_names:
            module = first(s for s in reversed(self.scopes) if s.is_module)
            for name in self.global_names:
                nodes = self.unscoped_names.pop(name, [])
                module.add(name, *nodes)

        # TODO: add nonlocal support here

        # Detect local names
        for name, nodes in self.unscoped_names.items():
            if any(isa(ast.Store, ast.Del, ast.Param), nodes):
                self.scope.add(name, *nodes)
                # ...

        return self.scopes.pop()


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
        self.unscoped_names[node.id].append(node)

    def visit_Global(self, node):
        self.global_names.update(node.names)

        # # Don't work if global or nonlocal is in use
        # if isinstance(node.ctx, (ast.Store, ast.Del))
        #     self.scope.add(node.id, node)
        # else:
        #     self.unscoped_names.append(node)



sb = ScopeBuilder()
scope = sb.visit(tree)
print scope
