GLOBAL_USAGE = []


def register_global_usage(func):
    GLOBAL_USAGE.append(func)


def run_global_usage(files, used):
    for func in GLOBAL_USAGE:
        func(files, used)
