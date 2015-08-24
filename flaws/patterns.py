import ast
import inspect
import sys
import textwrap

from funcy import zipdict, is_list, keep
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

class MapLambda(Pattern):
    def template(body=ast.expr, seq=ast.expr):
        map(lambda var: body, seq)

    def suggestion():
        [body for var in seq]


def match(template, tree):
    print 'tree'
    print astor.dump(tree)
    print 'template'
    print astor.dump(template)
    print '*' * 80
    stack = []
    potential = []
    matches = []

    def _match(node):
        print 'stack', stack, 'node', node

        # Check if any potential fails here
        next_potential = []
        for p in potential:
            if stack[:len(p['stack'])] != p['stack']:
                # Potential match can't fail
                print 'confirm', p
                matches.append(p)
            else:
                path = stack[len(p['stack']):]
                print 'path', path
                sub_template = get_sub_template(template, path)
                print 'sub', sub_template
                if node_matches(node, sub_template, p['context']):
                    print 'matches', node, sub_template, 'at', path
                    next_potential.append(p)
                else:
                    print 'discard', p
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
            print 'potential', potential[-1]

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
    # print 'get_sub_template', path
    sub = template
    for el in path:
        # print el
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
        # print sub
    return sub


def compile_template(func):
    spec = inspect.getargspec(func)
    assert len(spec.args) == len(spec.defaults or []), "All template args should have AST classes"

    compiler = TemplateCompiler(zipdict(spec.args, spec.defaults or []))
    template = map(compiler.visit, get_body_ast(func))
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
            def match_capture(n, context):
                if not isinstance(n, self.args[node.id]):
                    return False

                context['captures'][node.id] = n

                # Sticky variable names
                if self.args[node.id] == ast.Name:
                    if (node.id in context['names']) != (n.id in context['rev']):
                        return False
                    if node.id in context['names']:
                        return n.id == context['names'][node.id]
                    else:
                        context['names'][node.id] = n.id
                        context['rev'][n.id] = node.id
                        return True

                return True

            return match_capture
        else:
            return node
