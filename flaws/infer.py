import operator
from collections import deque
import ast

from .asttools import nodes_str
from funcy import joining


# class Unknown(object):
#     def __str__(self):
#         return '?'
_UNKNOWN = object()

class ValueInfo(object):
    def __init__(self, value=_UNKNOWN, typ=_UNKNOWN):
        self.value = value
        self.typ = typ
        self.rels = []

    def __str__(self):
        @joining('')
        def _str():
            if self.value is not _UNKNOWN:
                yield self.value
            if self.typ is not _UNKNOWN:
                yield ':' + str(self.typ)
            if self.rels:
                yield '~' + ','.join('%s-%s' % rel for rel in self.rels)

        return _str() or '?'

    def add_rel(self, op, value):
        self.rels.append((op, value))

    def __add__(self, other):
        if isinstance(self.value, (int, long, float)) \
                and isinstance(other.value, (int, long, float)):
            return ValueInfo(self.value + other.value)
        else:
            return ValueInfo()

# UNKNOWN = ValueInfo()


class Env(object):
    def __init__(self, scope):
        self.scope = scope
        self.locals = {}


import astor

class Inferer(astor.ExplicitNodeVisitor):
    def __init__(self):
        self.envs = deque()

    # Env mechanics
    @property
    def env(self):
        if self.envs:
            return self.envs[-1]
        else:
            return None

    def push_env(self, node):
        self.envs.append(Env(node.scope))

    def pop_env(self):
        self.envs.pop()


    def visit_Module(self, node):
        self.push_env(node)
        self.generic_visit(node)
        self.pop_env()

    def visit_Assign(self, node):
        self.generic_visit(node)
        # print node.__class__, node.__dict__
        if len(node.targets) == 1:
            target = node.targets[0]
            assert isinstance(target, ast.Name)
            target.val = node.value.val
            self.env.locals[target.id] = target.val
        else:
            for t in node.targets:
                t.val = ValueInfo()

    def visit_Name(self, node):
        node.val = self.env.locals.get(node.id) or ValueInfo()

    # def visit_Print(self, node):
    #     self.generic_visit(node)
    #     # print node.__class__, node.__dict__
    #     # node.val = self.env.locals.get(node.id, UNKNOWN)

    def visit_Expr(self, node):
        self.generic_visit(node)
        # node.val = node.value.val

    def visit_BinOp(self, node):
        self.visit(node.left)
        self.visit(node.right)
        node.left.val.add_rel(node.op.__class__.__name__, node.right.val)
        node.val = OPS[node.op.__class__](node.left.val, node.right.val)

    def visit_Num(self, node):
        node.val = ValueInfo(node.n)

    def visit_Str(self, node):
        # print node.__class__, node.__dict__
        node.val = ValueInfo(node.s)


OPS = {
    # ast.Lt:    '<',
    # ast.LtE:   '<=',
    # ast.Gt:    '>',
    # ast.GtE:   '>=',
    # ast.Eq:    '==',
    # ast.NotEq: '!=',
    # ast.In:    'in',
    # Is | IsNot | NotIn

    ast.Add:    operator.__add__,
    ast.Sub:    operator.__sub__,
    # ast.Mult:   '*',
    # ast.Div:    '/',
    # ast.LShift: '<<',
    # ast.RShift: '>>',
    # ast.BitOr:  '|',
    # ast.BitXor: '^',
    # ast.BitAnd: '&',
    # ast.Mod:    '%',
    # ast.Pow: '',
    # ast.FloorDiv: '',

    # ast.And:    '&&',
    # ast.Or:     '||',

    # ast.Invert: '~',
    # ast.Not:    '!',
    # ast.UAdd:   '+',
    # ast.USub:   '-',
}
