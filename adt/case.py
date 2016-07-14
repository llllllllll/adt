from inspect import signature
from functools import partial

from fz import placeholder
from toolz import curry

from .adt import mk_prepare_structure, Constructor as ADTConstructor


class Constructor(ADTConstructor):
    __slots__ = '_constructors',

    def __init__(self, constructors, name, *args, **kwargs):
        super().__init__(constructors, name, *args, **kwargs)
        del constructors[name]
        self._constructors = constructors

    def __rshift__(self, other):
        if callable(other):
            args = signature(other).parameters
            expr = other
        else:
            args = ()
            expr = lambda other=other: other

        positional_names = set(a._name for a in self._args)
        keyword_names = {v._name: k for k, v in self._kwargs.items()}
        new_names = positional_names | keyword_names.keys()
        used_args = set()
        used_kwargs = {}
        for n, argname in enumerate(args):
            if argname not in new_names:
                raise NameError('name %r not defined' % argname)
            if argname in positional_names:
                used_args.add(n)
            else:
                used_kwargs[argname] = keyword_names[argname]

        self._constructors[self._name] = a = Alternative(
            self._name,
            len(self._args),
            self._kwargs.keys(),
            tuple(used_args),
            used_kwargs,
            expr,
        )
        return a


class NoMatch(Exception):
    """Raised to indicate that the alternative does not match the expression.
    """


class Alternative:
    __slots__ = (
        '_constructor_name',
        '_nargs',
        '_kwargkeys',
        '_used_args',
        '_used_kwargs',
        '_expr',
    )

    def __init__(self,
                 constructor_name,
                 nargs,
                 kwargkeys,
                 used_args,
                 used_kwargs,
                 expr):
        self._constructor_name = constructor_name
        self._nargs = nargs
        self._kwargkeys = kwargkeys
        self._used_args = used_args
        self._used_kwargs = used_kwargs
        self._expr = expr

    def scrutinize(self, scrutine):
        constructor = type(scrutine)
        if constructor.__name__ != self._constructor_name:
            raise NoMatch()
        args = scrutine._args
        kwargs = scrutine._kwargs
        return self._expr(
            *(args[n] for n in self._used_args),
            **{k: kwargs[v] for k, v in self._used_kwargs.items()}
        )

    def __repr__(self):
        return self._constructor_name


def scrutinize(alternatives, scrutinee):
    # validate the case statement based on the scrutinee
    adt = scrutinee._adt
    constructors = {
        c._name: (len(c._args), c._kwargs.keys()) for c in adt._constructors
    }
    for alternative in alternatives:
        name = alternative._constructor_name
        if name not in constructors:
            raise TypeError(
                '%r is not a valid constructor of type: %r' % (name, adt),
            )
        nargs, kwargkeys = constructors[name]
        if alternative._nargs != nargs:
            raise TypeError(
                'invalid alternative for %r constructor, expected %d'
                ' positional arguments but received %d' % (
                    name,
                    nargs,
                    alternative._nargs,
                ),
            )
        if alternative._kwargkeys != kwargkeys:
            raise TypeError(
                'invalid alternative for %r constructor, mismatched keyword'
                ' arguments, expected %s but received %s' % (
                    name,
                    set(kwargkeys),
                    set(alternative._kwargkeys),
                ),
            )

    for alternative in alternatives:
        try:
            return alternative.scrutinize(scrutinee)
        except NoMatch:
            pass
    raise NoMatch(
        'No alternatives matched the given scrutinee: %r, tried the'
        ' following constructors:\n%s' % (
            scrutinee,
            '\n'.join(map(repr, alternatives)),
        ),
    )


def no_recursive_type(*args, **kwargs):
    raise TypeError('cannot use recursive types in case statements')


class CaseMeta(type):
    _marker = object()

    def __new__(mcls, name, bases, dict_):
        if bases and bases[0] is mcls._marker:
            return super().__new__(mcls, name, (), dict_)

        for name in ('__module__', '__qualname__'):
            del dict_[name]

        if dict_:
            raise TypeError(
                'Case dictionaries should only contain alternatives, got: %r' %
                dict_
            )

        return partial(scrutinize, dict_._constructors.values())

    __prepare__ = mk_prepare_structure(
        no_recursive_type,
        Constructor,
        placeholder,
    )


class case(CaseMeta._marker, metaclass=CaseMeta):
    """Convenience for creating case statements.
    """


@curry
def match(data, case):
    """Sugar for matching a case statement.

    Examples
    --------
    >>> @match(data)
    ... class result(case):
    ...     Constructor(...) >> some_expr
    ...     ...
    """
    return case(data)
