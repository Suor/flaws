#!/usr/bin/env python
import sys

from funcy import split, map

from .analysis import global_usage, local_usage, FileSet


import sys, ipdb, traceback

def info(type, value, tb):
    traceback.print_exception(type, value, tb)
    print
    ipdb.pm()

sys.excepthook = info


def main():
    command = sys.argv[1]
    kwargs, args = split(r'^--', sys.argv[2:])
    kwargs = dict(map(r'^--(\w+)=(.+)', kwargs))

    from .ext import django
    django.register(args, kwargs)

    files = FileSet(args, base=kwargs.get('base'), ignore=kwargs.get('ignore'))
    if command == 'global':
        global_usage(files)
    elif command == 'local':
        local_usage(files)
    else:
        print 'Unknown command', command


if __name__ == '__main__':
    main()
