import ast

from funcy import keep, partial, cat, ikeep, project

from ..asttools import ast_eval, is_name
from . import register_global_usage


def register(args, kwargs):
    # settings_module = kwargs['settings']
    # extra_urlconf = kwargs['urlconf']
    register_global_usage(partial(global_usage, opts=project(kwargs, ['settings', 'urlconf'])))


def global_usage(files, used, opts={}):
    if 'settings' not in opts:
        return
    settings = files[opts['settings']]

    urlconfs = [get_name_val(settings.scope.names['ROOT_URLCONF'][0])]
    if opts.get('urlconf'):
        urlconfs.append(opts['urlconf'])

    for urlconf in urlconfs:
        used[urlconf].add('urlpatterns')

        views = _parse_urlconf(files, files[urlconf])
        views = [v.rsplit('.', 1) for v in views if '.' in v]
        for module, view in views:
            used[module].add(view)


def _parse_urlconf(files, urlconf):
    is_patterns = lambda node: isinstance(node, ast.Call) and is_name(node.func, 'patterns')
    patterns = filter(is_patterns, ast.walk(urlconf.tree))
    return cat(_parse_patterns(files, p) for p in patterns)


def _parse_patterns(files, call_node):
    if len(call_node.args) < 2 or not isinstance(call_node.args[0], ast.Str):
        return []

    views_module = ast_eval(call_node.args[0])
    views = []

    for node in ikeep(_parse_urlrec, ast.walk(call_node)):
        if isinstance(node, ast.Str):
            views.append(ast_eval(node))
        elif isinstance(node, ast.Call) and is_name(node.func, 'include') \
                and len(node.args) >= 1 and isinstance(node.args[0], ast.Str):
            subconf = ast_eval(node.args[0])
            if subconf in files:
                views.extend(_parse_urlconf(files, files[subconf]))

    if views_module:
        views = ['%s.%s' % (views_module, v) for v in views]
    return views


def _parse_urlrec(node):
    if isinstance(node, ast.Call) and len(node.args) >= 2:
        return node.args[1]
    elif isinstance(node, ast.Tuple) and len(node.elts) >= 2:
        return node.elts[1]


def get_name_val(node):
    assert isinstance(node, ast.Name) and isinstance(node.up, ast.Assign)

    assign = node.up
    assert len(assign.targets) == 1

    return ast_eval(assign.value)
