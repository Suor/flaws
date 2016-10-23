#!/usr/bin/env python
import sys

from funcy import split, map

from .analysis import global_usage, local_usage, FileSet


def main():
    command = sys.argv[1]
    kwargs, args = split(r'^--', sys.argv[2:])
    kwargs = dict(map(r'^--(\w+)(?:=(.+))?', kwargs))

    # Run ipdb on exception
    if 'ipdb' in kwargs:
        import ipdb, traceback

        def info(type, value, tb):
            traceback.print_exception(type, value, tb)
            print
            ipdb.pm()

        sys.excepthook = info

    # Register plugins
    from .ext import django
    django.register(args, kwargs)

    # Do the job
    files = FileSet(args, base=kwargs.get('base'), ignore=kwargs.get('ignore'))
    if command == 'global':
        global_usage(files)
    elif command == 'local':
        local_usage(files)
    else:
        print 'Unknown command', command


if __name__ == '__main__':
    main()
