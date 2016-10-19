import ast

from funcy import partial, cat, ikeep, project, imapcat, any

from ..asttools import ast_eval, is_name
from . import register_global_usage


def register(args, kwargs):
    register_global_usage(partial(global_usage, opts=project(kwargs, ['settings', 'urlconf'])))


def global_usage(files, used, opts={}):
    mark_used_settings(files, used, opts=opts)
    mark_used_views(files, used, opts=opts)

    # Mark migrations
    for package, _ in files.items():
        if 'migrations.' in package:
            # Justification for models:
            #   - do not bother people with unused import in write-once files
            used[package].update({'Migration', 'models'})

    # Mark commands
    for package, _ in files.items():
        if 'management.commands.' in package:
            used[package].add('Command')

    # Mark registered tags and translations
    mark_registered(files, used)


def mark_registered(files, used):
    def is_register(node):
        reg_names = {'register', 'library'}
        return isinstance(node, ast.Name) and node.id in reg_names \
            or isinstance(node, ast.Attribute) and node.attr in reg_names

    for package, pyfile in files.items():
        for name, nodes in pyfile.scope.names.items():
            adef = nodes[0]
            if not is_def(adef):
                continue

            if any(is_register, imapcat(ast.walk, adef.decorator_list)):
                used[package].add(name)


def mark_used_settings(files, used, opts={}):
    settings = files.get(opts.get('settings'))

    if settings:
        for name, nodes in settings.scope.names.items():
            node = nodes[0]
            if is_assign(node) and node.id.isupper():
                used[settings.package].add(name)


def mark_used_views(files, used, opts={}):
    settings = files.get(opts.get('settings'))
    urlconfs = []

    # Get root urlconf from settings, the check is needed in case
    if settings:
        root_urlconf = get_name_val(settings.scope.names['ROOT_URLCONF'][0])
        if root_urlconf in files:
            urlconfs.append(root_urlconf)
    # Get urlconf from options
    if opts.get('urlconf'):
        urlconfs.append(opts['urlconf'])

    # TODO: warn about no urlconf
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


def is_assign(node):
    return isinstance(node, ast.Name) \
            and isinstance(node.ctx, ast.Store)

def is_def(node):
    return isinstance(node, (ast.FunctionDef, ast.ClassDef))
