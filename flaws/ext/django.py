import ast
import re

from funcy.py2 import partial, cat, ikeep, project, imapcat, any

from ..asttools import ast_eval, is_name, is_call
from . import register_global_usage


def register(args, kwargs):
    register_global_usage(partial(global_usage, opts=project(kwargs, ['settings', 'urlconf'])))


def global_usage(files, used, opts={}):
    mark_used_settings(files, used, opts=opts)
    mark_used_views(files, used, opts=opts)

    # Mark default app confs
    for package, pyfile in files.items():
        if 'default_app_config' in pyfile.scope.names:
            used[package].add('default_app_config')

            conf = ast_eval(pyfile.scope.names['default_app_config'][0].up.value)
            _mark_refs(files, used, [conf])

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
        reg_names = {'register', 'library', 'receiver'}
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
            if is_store(node) and node.id.isupper():
                used[settings.package].add(name)

                # Things refered by their string path
                if isinstance(node.up, ast.Assign):
                    refs = [n.s for n in ast.walk(node.up.value)
                                if isinstance(n, ast.Str) and re.search(r'^\w+(?:\.\w+)+$', n.s)]

                    _mark_refs(files, used, refs)

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
        _mark_refs(files, used, _parse_urlconf(files, files[urlconf]))


def _parse_urlconf(files, urlconf):
    # Old patterns() call, TODO: drop them
    patterns = [n for n in ast.walk(urlconf.tree) if is_call(n, 'patterns')]
    if patterns:
        return cat(_parse_patterns(files, p) for p in patterns)

    # NOTE that we don't support mixing patterns() and new style in single file
    refs = [n.args[1].s for n in ast.walk(urlconf.tree) if is_call(n, 'url') and
            len(n.args) >= 2 and isinstance(n.args[1], ast.Str)]

    included = [n.args[0].s for n in ast.walk(urlconf.tree) if is_call(n, 'include') and
                len(n.args) >= 1 and isinstance(n.args[0], ast.Str)]
    for mod in included:
        if mod in files:
            refs.append('%s.urlpatterns' % mod)
            refs.extend(_parse_urlconf(files, files[mod]))

    return refs

def _parse_patterns(files, call_node):
    if len(call_node.args) < 2 or not isinstance(call_node.args[0], ast.Str):
        return []

    views_module = ast_eval(call_node.args[0])
    refs = []

    for node in ikeep(_parse_urlrec, ast.walk(call_node)):
        if isinstance(node, ast.Str):
            refs.append(ast_eval(node))
        elif isinstance(node, ast.Call) and is_name(node.func, 'include') \
                and len(node.args) >= 1 and isinstance(node.args[0], ast.Str):
            subconf = ast_eval(node.args[0])
            if subconf in files:
                refs.append('%s.urlpatterns' % subconf)
                refs.extend(_parse_urlconf(files, files[subconf]))

    if views_module:
        refs = ['%s.%s' % (views_module, v) for v in refs]
    return refs

def _parse_urlrec(node):
    if isinstance(node, ast.Call) and len(node.args) >= 2:
        return node.args[1]
    # TODO: drop old tuple style
    elif isinstance(node, ast.Tuple) and len(node.elts) >= 2:
        return node.elts[1]


def _mark_refs(files, used, refs):
    for ref in refs:
        module, func = ref.rsplit('.', 1)
        if module in files:
            used[module].add(func)


def get_name_val(node):
    assert isinstance(node, ast.Name) and isinstance(node.up, ast.Assign)

    assign = node.up
    assert len(assign.targets) == 1

    return ast_eval(assign.value)


def is_store(node):
    return isinstance(node, ast.Name) \
            and isinstance(node.ctx, ast.Store)

def is_def(node):
    return isinstance(node, (ast.FunctionDef, ast.ClassDef))
