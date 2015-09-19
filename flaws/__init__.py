#!/usr/bin/env python
import os
import sys
import ast
import re

from funcy import all, imapcat, split, map
import astor

from .asttools import (is_write, is_use, is_constant, is_param, is_import,
                       name_class, node_str, to_source)
from .scopes import fill_scopes
from .infer import Inferer
from .utils import slurp
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
