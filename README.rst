Iron
====

A tool to iron out your python code.

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
- reusing name for different purpose
- reusing name with a change of type
- predict TypeErrors by type inferencing
- name giving wrong hint about its type, e.g. smiles_dict being a list

Globally:

- unused/not exported functions/classes/variables
- unused parameters
- wrong defaults for parameters (always overridden)
- globally dead code
- global type inferencing?

Style?:

- c-style loops
- loops by index
- use generator expression instead of list comprehension
- don't use unneeded parentheses in generator expression
- use map/list comprehension instead of for/list.append loop
- use defaultdicts and deque instead of dicts and lists where appropriate
- use iterator versions of map()/fiter()/... where appropriate
- use list comprehension instead of map(lambda)/filter(lambda)
- built-in overrides

