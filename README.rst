Iron
====

A python code static analyzer. Catches common errors.

Under development, doesn't even work yet.


Plans
-----

Things to catch:

- find undefined names (possible typos)
- unused imports
- unused variables/values/parameters
- unused/not exported functions/classes
- unused private methods
- commented out code
- commented out debug code
- debug prints? debug code?
- dead code
- dead conditions (if True or ...:)

Globally:

- unused/not exported functions/classes/variables
- unused parameters
- wrong defaults for parameters (always overridden)
- globally dead code
- global type inferencing?
- outdated dependencies in requirements.txt or setup.py?

Style:

- c-style loops
- loops by index
- use generator expression instead of list comprehension
- don't use unneeded parentheses in generator expression
- use map/list comprehension instead of for/list.append loop
- use defaultdicts and deque instead of dicts and lists where appropriate
- use iterator versions of map()/filter()/... where appropriate
- use list comprehension instead of map(lambda)/filter(lambda)
- built-in overrides
- parentheses in if, while
- for list.append -> list.extend
- not using negative indexing, i.e. arr[len(arr)-1]

Type inference and stuff:

- predict TypeErrors by type inferencing
- range inference and checking?
- name giving wrong hint about its type, e.g. smiles_dict being a list
- reusing name for different purpose
- reusing name with a change of type
- functions returning different types, e.g. ints and lists on different occasions
