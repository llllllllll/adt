===
ADT
===

Algebraic data types for Python.


.. todo::

   Write a better readme


Basic Usage
===========

Defining Types
--------------

To define a new type, create a subclass of ``adt.ADT`` where the class body
contains the constructors.

A constructor is a capitalized name which may be parameterized on some
types. Type variables are denoted with ``_1``, ``_2``, ``_3``, and so on.

The order of the types when we instantiate ADTs is the order of the type
variable's number. So ``_1`` is bound to the first type, ``_2`` to the second
and so on.

The following example have **only** imported ``ADT`` from the ``adt``
module. The constructor names and type variable names are **not** defined before
hand.

``Either[_1, _2]``
~~~~~~~~~~~~~~~~~~

Define an ``Either`` type.

.. code-block:: python

   class Either(ADT):
       Left(_1)
       Right(_2)


To create instances of this type, we would do something like:

.. code-block:: python

   >>> Either[int, float].Left(1)  # box an int value
   Either[int, float].Left(1)
   >>> Either[int, float].Right(1.5)  # box a float value
   Either[int, float].Right(1.5)


We cannot create invalid instances, for example:

.. code-block:: python

   >>> Either[int, float].Right(1)  # the ``Right`` constructor takes floats,
   ...                              # not ints
   Traceback (most recent call last):
      ...
   TypeError: expected type 'float' for argument at position 0, got 'int': 1


``Struct[_1, _2]``
~~~~~~~~~~~~~~~~~~

Define a type with named values.

.. code-block:: python

   class Struct(ADT):
      A(a=_1, b=_1)
      B(a=_2, b=_2)


Instances must be created with keyword arguments, for example:

.. code-block:: python

   >>> Struct[int, float].A(a=1, b=2)
   Struct[int, float].A(b=2, a=1)

We can access the fields by name:

.. code-block:: python

   >>> s = Struct[int, float].A(a=1, b=2)
   >>> s.a
   1
   >>> s.b
   2


``List[_1]``
~~~~~~~~~~~~

We can create recursive structures:

.. code-block::

   class List(ADT):
       Nil()
       Cons(_1, List[_1])


It is enforced that the list on the right side of a ``Cons`` cell holds the same
type as the left side.


Destructuring Types
-------------------

We create these types so that we may use them in ``case`` statements.

Case statements have the following syntax:

.. code-block:: python

   from adt import case, match

   @match(scrutinee)
   class value(case):
       Constructor1(arg1, arg2, ... argn) >> expr1
       Constructor2(arg1, arg2, ... argn) >> expr2
       ...
       Constructorn(arg1, arg2, ... argn) >> exprn


This says that when the expression ``scrutinee`` is an instance of
``Constructorn``, then ``value`` will be the result of executing ``exprn`` with
``arg1, arg2, ... argn`` in scope.

For example:

.. code-block:: python

   >>> @print
   ... @match(Either[int, float].Left(1))
   ... class _(case):
   ...     Right(_1) >> float('nan')
   ...     Left(_1) >> _1 + 1
   2

   >>> @print
   ... @match(Struct[int, float].A(a=1, b=2))
   ... class _(case):
   ...     A(a=_1, b=_2) >> _1 + _2
   ...     B(a=_1, b=_2) >> _1 - _2
   3

   >>> @print
   ... @match(List[int].Cons(1, List[int].Nil()))
   ... class _(case):
   ...     Nil() >> 'empty'
   ...     Cons(_1, _2) >> 'not empty'
   not empty


Why?
====

This is valid python syntax.
