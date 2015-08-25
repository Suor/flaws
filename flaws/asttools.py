import ast


def is_write(node):
    return isinstance(node, (ast.Import, ast.ImportFrom,
                             ast.FunctionDef, ast.ClassDef, ast.arguments)) \
        or isinstance(node.ctx, (ast.Store, ast.Del, ast.Param))

def is_use(node):
    return isinstance(node, ast.Name) \
        and isinstance(node.ctx, (ast.Load, ast.Del))

def is_constant(node):
    return isinstance(node, ast.Name) and node.id.isupper()

def is_param(node):
    return isinstance(node, ast.Name) and isinstance(node.ctx, ast.Param) \
        or isinstance(node, ast.arguments)

def is_import(node):
    return isinstance(node, (ast.Import, ast.ImportFrom))


def ast_eval(node):
    if isinstance(node, (ast.List, ast.Tuple)):
        return map(ast_eval, node.elts)
    elif isinstance(node, ast.Str):
        return node.s
    elif isinstance(node, ast.Num):
        return node.n
    else:
        raise ValueError("Don't know how to eval %s" % node.__class__.__name__)


def name_class(node):
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return 'import'
    elif isinstance(node, ast.FunctionDef):
        return 'function'
    elif isinstance(node, ast.ClassDef):
        return 'class'
    elif is_param(node):
        return 'param'
    else:
        return 'variable'

def node_str(node):
    return '%s at %d:%d' % (name_class(node), node.lineno, node.col_offset)

def nodes_str(nodes):
    return '[%s]' % ', '.join(map(node_str, nodes))


# Parse to AST

import sys
import inspect
import textwrap

def get_body_ast(func):
    return get_ast(func).body[0].body

def get_ast(func):
    # Get function source
    source = inspect.getsource(func)
    source = textwrap.dedent(source)

    # Preserve line numbers
    source = '\n' * (func.__code__.co_firstlineno - 2) + source

    return ast.parse(source, func_file(func), 'single')

def func_file(func):
    return getattr(sys.modules[func.__module__], '__file__', '<nofile>')


# Code generation

from astor.codegen import SourceGenerator
from termcolor import colored

def to_source(node, indent_with=' ' * 4, add_line_information=False):
    """
    A modified to_source() function from astor.
    """
    generator = AnnotatedSourceGenerator(indent_with, add_line_information)
    generator.visit(node)
    return ''.join(str(s) for s in generator.result)


class AnnotatedSourceGenerator(SourceGenerator):
    def visit(self, node):
        SourceGenerator.visit(self, node)
        if not isinstance(node, (ast.Num, ast.Str)) and hasattr(node, 'val'):
            self.write(colored(' (%s)' % node.val, 'green'))
