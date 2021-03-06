import ast
import inspect

from funcy.py2 import zipdict, is_list, keep, partial
from funcy.py3 import lmap
import astor

from .asttools import get_body_ast


class Pattern(object):
    pass

class UselessIf(Pattern):
    def template(cond=ast.expr):
        if cond:
            return True
        else:
            return False

    def suggestion():
        return bool(cond)

    # return True if a != 2 else False
    # else if ...:
    #
    # if n % 400 == 0:
    #     return True
    # elif n % 100 == 0:
    #     return False
    # elif n % 4 == 0:
    #     return True
    # else:
    #     return False

    # if y<=x:
    #     if x<=z:
    #         return True
    #     else:
    #         return False
    # else:
    #     return False
    #
    # y <= x and x <= z

class MapLambda(Pattern):
    def template(body=ast.expr, seq=ast.expr):
        map(lambda var: body, seq)

    def suggestion():
        [body for var in seq]


def match(template, tree):
    stack = []
    potential = []
    matches = []

    def _match(node):
        # Check if any potential fails here
        next_potential = []
        for p in potential:
            if stack[:len(p['stack'])] != p['stack']:
                # Potential match can't fail
                matches.append(p)
            else:
                path = stack[len(p['stack']):]
                sub_template = get_sub_template(template, path)
                if node_matches(node, sub_template, p['context']):
                    next_potential.append(p)
        potential[:] = next_potential

        # Check if template starts here
        context = {'names': {}, 'rev': {}, 'captures': {}}
        if node_matches(node, template, context):
            # potential.append((stack[:], node[0]))
            potential.append({
                'stack': stack[:],
                # Always refer to a first node even when template is a list
                'node': node[0] if is_list(node) else node,
                'context': context,
            })

        # Go deeper
        if isinstance(node, ast.AST):
            for name, value in ast.iter_fields(node):
                stack.append(name)
                _match(value)
                stack.pop()
        elif isinstance(node, list) and node:
            # NOTE: we treat lists as recursive data structures here.
            #       0 means go to list head, 1 to tail.
            stack.append(0)
            _match(node[0])
            stack.pop()

            stack.append(1)
            _match(node[1:])
            stack.pop()

    _match(tree)

    results = []
    for m in matches + potential:
        m['node'].captures = m['context']['captures']
        results.append(m['node'])
    return results

def node_matches(node, template_node, context):
    if isinstance(template_node, ast.AST):
        return type(node) is type(template_node)
    elif isinstance(template_node, list):
        return isinstance(node, list) and len(node) >= len(template_node) \
            and (template_node == [] or node_matches(node[0], template_node[0], context))
    elif template_node is None:
        return node is None
    elif isinstance(template_node, (str, int, float)):
        return node == template_node
    else:
        return template_node(node, context)

def get_sub_template(template, path):
    sub = template
    for el in path:
        # TODO: optimize it
        if el == 0:
            try:
                sub = sub[0]
            except IndexError:
                return lambda node, _: False
        elif el == 1:
            sub = sub[1:]
        elif isinstance(sub, ast.AST) and el in sub._fields:
            sub = getattr(sub, el)
        elif callable(sub):
            return lambda node, _: True
        else:
            raise Exception('Unknown path', path, 'in', astor.dump(sub))
    return sub


def compile_template(func):
    spec = inspect.getargspec(func)
    assert len(spec.args) == len(spec.defaults or []), "All template args should have AST classes"

    compiler = TemplateCompiler(zipdict(spec.args, spec.defaults or []))
    template = lmap(compiler.visit, get_body_ast(func))
    # Strip Expr node wrapping single expression to let it match inside statement
    if len(template) == 1 and isinstance(template[0], ast.Expr):
        return template[0].value
    return template


class TemplateCompiler(ast.NodeTransformer):
    def __init__(self, args):
        self.args = args

    def generic_visit(self, node):
        """
        Modified .generic_visit() from NodeTransformer allows callables in tree.
        """
        for field, old_value in ast.iter_fields(node):
            old_value = getattr(node, field, None)
            if isinstance(old_value, list):
                old_value[:] = keep(self.visit, old_value)
            elif isinstance(old_value, ast.AST):
                new_node = self.visit(old_value)
                if new_node is None:
                    delattr(node, field)
                else:
                    setattr(node, field, new_node)
        return node

    def visit_Attribute(self, node):
        if isinstance(node.value, ast.Name) and node.value.id == 'ast':
            cls = getattr(ast, node.attr)
            return lambda n, _: isinstance(n, cls)
        else:
            return node

    def visit_Name(self, node):
        if node.id in {'True', 'False', 'None'}:
            return node
        elif node.id in self.args:
            return partial(match_capture, node.id, self.args[node.id])
        else:
            return node

    def visit_arg(self, node):
        print('visit_arg', node)
        if node.arg in self.args:
            return partial(match_capture, node.arg, self.args[node.arg])
        else:
            return node


def match_capture(arg_name, arg_template, node, context):
    if not isinstance(node, arg_template):
        return False

    context['captures'][arg_name] = node

    # Sticky variable names
    if arg_template is ast.Name:
        if (arg_name in context['names']) != (node.id in context['rev']):
            return False
        if arg_name in context['names']:
            return node.id == context['names'][arg_name]
        else:
            context['names'][arg_name] = node.id
            context['rev'][node.id] = arg_name
            return True

    return True
