import ast

from funcy import keep, partial

from ..asttools import ast_eval
from . import register_global_usage


def register(args):
    settings_module = keep(r'--settings=([\w\.]+)', args)[0]
    register_global_usage(partial(global_usage, settings_module))


def global_usage(settings_module, files, used):
    settings = files[settings_module]

    root_urlconf_module = get_name_val(settings.scope.names['ROOT_URLCONF'][0])
    used[root_urlconf_module].add('urlpatterns')
    root_urlconf = files[root_urlconf_module]
    views = _parse_urlconf(root_urlconf)
    for module, view in views:
        used[module].add(view)

    # from IPython import embed; embed()


def _parse_urlconf(urlconf):
    var_node = urlconf.scope.names['urlpatterns'][0]
    assert isinstance(var_node, ast.Name) and isinstance(var_node.up, ast.Assign)

    call_node = var_node.up.value
    assert isinstance(call_node, ast.Call) and len(call_node.args) >= 1

    views_module = ast_eval(call_node.args[0])
    urls = call_node.args[1:]
    views = keep(_parse_urlrec, urls)

    if views_module:
        views = ['%s.%s' % (views_module, v) for v in views]

    return [v.rsplit('.', 1) for v in views]


def _parse_urlrec(rec):
    if isinstance(rec, ast.Call) and isinstance(rec.args[1], ast.Str):
        return ast_eval(rec.args[1])


def get_name_val(node):
    assert isinstance(node, ast.Name) and isinstance(node.up, ast.Assign)

    assign = node.up
    assert len(assign.targets) == 1

    return ast_eval(assign.value)
