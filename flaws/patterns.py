import ast
import inspect
import sys
import textwrap

from funcy import isa
import astor


class Pattern(object):
    pass

class UselessIf(Pattern):
    def template():
        if ast.expr:
            return True
        else:
            return False


def match_tree(tree):
    print 'tree'
    print astor.dump(tree)
    print 'template'
    template = get_body_ast(UselessIf.template)
    template = map(TemplateCompiler().visit, template)
    print astor.dump(template)

    matching_nodes = match(template, tree)
    return [
        {'type': 'useless_if', 'lineno': node.lineno}
        for node in matching_nodes
    ]

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
        p = []
        for start_stack, start_node in potential:
            if stack[:len(start_stack)] != start_stack:
                # Potential match can't fail
                print 'confirm', start_stack, start_node
                matches.append((start_stack, start_node))
            else:
                path = stack[len(start_stack):]
                print 'path', path
                sub_template = get_sub_template(template, path)
                print 'sub', sub_template
                if node_matches(node, sub_template):
                    print 'matches', node, sub_template, 'at', path
                    p.append((start_stack, start_node))
                else:
                    print 'discard', start_stack, start_node
        potential[:] = p

        # Check if template starts here
        if node_matches(node, template):
            potential.append((stack[:], node[0]))
            print 'potential', potential[-1]

        # Go deeper
        if isinstance(node, ast.AST):
            for name, value in ast.iter_fields(node):
                stack.append(name)
                _match(value)
                stack.pop()
        elif isinstance(node, list) and node:
            stack.append(0)
            _match(node[0])
            stack.pop()

            stack.append(1)
            _match(node[1:])
            stack.pop()
        else:
            pass # Don't need to go deeper on scalars

    _match(tree)
    return [node for _, node in matches + potential]

def node_matches(node, template_node):
    if isinstance(template_node, ast.AST):
        return type(node) is type(template_node)
    elif isinstance(template_node, list):
        return isinstance(node, list) and len(node) >= len(template_node) \
            and (template_node == [] or node_matches(node[0], template_node[0]))
    elif isinstance(template_node, (str, int, float)):
        return node == template_node
    else:
        return template_node(node)

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
                return lambda _: False
        elif el == 1:
            sub = sub[1:]
        elif isinstance(sub, ast.AST) and el in sub._fields:
            sub = getattr(sub, el)
        elif callable(sub):
            return lambda _: True
        else:
            raise Exception('Unknown path', path, 'in', astor.dump(sub))
        # print sub
    return sub


def compile_template(func):
    return map(TemplateCompiler().visit, get_body_ast(func))

class TemplateCompiler(ast.NodeTransformer):
    def visit_Attribute(self, node):
        if isinstance(node.value, ast.Name) and node.value.id == 'ast':
            cls = getattr(ast, node.attr)
            return  isa(cls)
        else:
            return node


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
