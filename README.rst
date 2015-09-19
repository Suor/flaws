Flaws
=====

A python code static analyzer. Catches common errors.

In early pre-alpha, but already does something useful. It catches:

- undefined names (possible typos)
- unused imports
- unused variables/values/parameters
- unused/not exported functions/classes/variables/constants

It also provides you with API to find templates in your code:

.. code:: python

    from flaws.patterns import compile_template, match

    def useless_ifelse(cond=ast.Expr):
        True if cond else False

    template = compile_template(useless_ifelse)
    nodes = match(template, tree)

    nodes[0]           # ast.IfExp(...)
    nodes[0].captures  # {'cond': ast.BinOp(...)}

Try this with your templates and against your own code and consider `leaving feedback <https://github.com/Suor/flaws/issues>`_.


Plans
-----

Things to catch:

- unused private methods
- commented out code
- commented out debug code
- debug prints? debug code?
- dead code
- dead conditions (if True or ...:)
- wrong except, e.g. except TypeError, ValueError
- forgotten returns

Globally:

- unused/not exported functions/classes/variables
- never passed parameters
- unused parameter defaults
- passing the same value to a parameter everywhere
- globally dead code
- global type inferencing?
- outdated dependencies in requirements.txt or setup.py?

Style:

- rewrite if cond: return True; else: False
- c-style loops
- loops by index
- use generator expression instead of list comprehension
- don't use unneeded parentheses in generator expression
- use map/list comprehension instead of for/list.append loop
- use map/filter instead of list/generator expression
- use defaultdicts and deque instead of dicts and lists where appropriate
- use iterator versions of map()/filter()/... where appropriate
- use list comprehension instead of map(lambda)/filter(lambda)
- built-in overrides
- parentheses in if, while
- for list.append -> list.extend
- needless slicing
- not using negative indexing, i.e. arr[len(arr)-1]
- not using built-in functions properly (_popget)
- passing defaults to functions, i.e. some_dict.get(key, None)
- find duplicate code

Type inference and stuff:

- predict TypeErrors by type inferencing
- range inference and checking?
- name giving wrong hint about its type, e.g. smiles_dict being a list
- reusing name for different purpose
- reusing name with a change of type
- functions returning different types, e.g. ints and lists on different occasions
- using class methods and attributes that don't exist

Value inferencing:

- unused value
- redefining a function/class/method in the same scope
- using a variable before setting it
- passing the wrong number of parameters to functions/methods/constructors
- passing the wrong number of parameters to builtin functions & methods
- using format strings that don't match arguments
- changing signature when overriding a method
- constructing a list when generator is enough
