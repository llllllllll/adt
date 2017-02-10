import builtins
from functools import partial
import sys

from lazy import thunk, strict, operator as op
from lazy.tree import LTree, Call, Normal
from toolz import curry, merge, valmap

from .adt import mk_prepare_structure, Constructor as ADTConstructor


class RegisteringThunk(thunk):
    def __new__(cls, *args, **kwargs):
        return super().__new__(cls, lambda: Constructor(*args, **kwargs))

    def __rshift__(self, other):
        return strict(self) >> other


def name_lookup(name):
    """A box to hold a name lookup, we lookup the value from the LTree.

    If we ever evaluate this it means that it didn't get subs'd out in the name
    substitution step so it was not in scope.
    """
    raise NameError(name)


class capture_string:
    def __init__(self):
        self.value = None

    def __eq__(self, other):
        if isinstance(other, str):
            self.value = other
            return True
        return False


class Constructor(ADTConstructor):
    __slots__ = '_constructors',

    @staticmethod
    def _unwrap_name(arg):
        name = capture_string()
        if LTree.parse(arg) != Call(Normal(name_lookup), (Normal(name),), {}):
            # this should actually be a recursive destructure like in haskell
            # but I haven't gotten to that yet
            raise SyntaxError("can't assign to expression")
        return name.value

    def __init__(self, constructors, name, *args, **kwargs):
        args = tuple(map(self._unwrap_name, args))
        kwargs = valmap(self._unwrap_name, kwargs)
        already_bound = {}
        for n, arg in enumerate(args):
            if arg in already_bound:
                raise TypeError(
                    'argument %r at position %d is already bound to the'
                    ' positional argument at index %d' % (
                        arg,
                        n,
                        already_bound[arg],
                    ),
                )
            already_bound[arg] = n

        for k, arg in kwargs.items():
            if arg in already_bound:
                loc = already_bound[arg]
                raise TypeError(
                    'argument %r at keyword %s is already bound to the %s' % (
                        arg,
                        k,
                        ('positional argument at index %d' % loc)
                        if isinstance(loc, int) else
                        ('keyword argument %r' % loc),
                    ),
                )

        super().__init__(constructors, name, *args, **kwargs)
        del constructors[name]
        self._constructors = constructors

    _literal_conversions = {
        list: lambda es: thunk(lambda *es: list(es), *es),
        set: lambda es: thunk(lambda *es: set(es), *es),
        tuple: lambda es: thunk(lambda *es: tuple(es), *es),
        dict: lambda d: thunk(dict, **d),
    }

    def _box_literal(self, collection):
        """We are not using ``lazy_function`` to wrap the class body so
        literal values are not thunks.
        """
        try:
            return self._literal_conversions[type(collection)](collection)
        except KeyError:
            return thunk.fromexpr(collection)

    def __rshift__(self, other):
        other = self._box_literal(other)
        if_not_alt = thunk(op.rshift, self, other)
        self._constructors[self._name] = Alternative(
            self._name,
            self._args,
            self._kwargs,
            other,
            if_not_alt,
        )
        return if_not_alt

    @staticmethod
    def __or__(other):
        return NotImplemented


class NoMatch(Exception):
    """Raised to indicate that the alternative does not match the expression.
    """


class Alternative:
    __slots__ = (
        '_constructor_name',
        '_argnames',
        '_kwargnames',
        '_expr',
        '_if_not_alt',
    )

    def __init__(self,
                 constructor_name,
                 argnames,
                 kwargnames,
                 expr,
                 if_not_alt):
        self._constructor_name = constructor_name
        self._argnames = argnames
        self._kwargnames = kwargnames
        self._expr = expr
        self._if_not_alt = if_not_alt

    def scrutinize(self, scrutine, context_frame):
        constructor = type(scrutine)
        if constructor.__name__ != self._constructor_name:
            raise NoMatch()

        kwargs = scrutine._kwargs
        # the context to evaluate the thunk in
        context = {
            Call(Normal(name_lookup), (Normal(name),), {}): Normal(value)
            for name, value in merge(
                vars(builtins),
                context_frame.f_globals,
                context_frame.f_locals,
                # the newly bound arguments have the highest precedence
                dict(zip(self._argnames, scrutine._args)),
                {v: kwargs[k] for k, v in self._kwargnames.items()},
            ).items()
        }
        bound_tree = LTree.parse(self._expr).subs(context)
        return strict(bound_tree.lcompile())

    def __repr__(self):
        return self._constructor_name


def scrutinize(alternatives, scrutinee, context_frame=None):
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
        if len(alternative._argnames) != nargs:
            raise TypeError(
                'invalid alternative for %r constructor, expected %d'
                ' positional arguments but received %d' % (
                    name,
                    nargs,
                    len(alternative._argnames),
                ),
            )
        if alternative._kwargnames.keys() != kwargkeys:
            raise TypeError(
                'invalid alternative for %r constructor, mismatched keyword'
                ' arguments, expected %s but received %s' % (
                    name,
                    set(kwargkeys),
                    set(alternative._kwargnames),
                ),
            )

    if context_frame is None:
        # the calling frame
        context_frame = sys._getframe(1)
    for alternative in alternatives:
        try:
            return alternative.scrutinize(scrutinee, context_frame)
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


@object.__new__
class everything:
    def __contains__(self, other):
        return True


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

        alttrees = {
            LTree.parse(alt._if_not_alt): alt
            for alt in dict_._constructors.values()
        }
        altconstructors = {
            k.args[0]: v for k, v in alttrees.items()
        }
        for alt, expr in alttrees.items():
            # drop the first element of the iter because it is the node itself
            for leaf in alt.leaves():
                try:
                    if altconstructors[leaf] is not expr:
                        del altconstructors[leaf]
                except (KeyError, TypeError):
                    pass

        return partial(scrutinize, altconstructors.values())

    __prepare__ = mk_prepare_structure(
        no_recursive_type,
        Constructor,
        partial(thunk, name_lookup),
        everything,
    )


class case(CaseMeta._marker, metaclass=CaseMeta):
    """Convenience for creating case statements.
    """


@curry
def match(data, case):
    """Sugar for matching a case statement.

    Examples
    --------
    >>> @match(data)  # doctest: +SKIP
    ... class result(case):
    ...     Constructor(...) >> some_expr
    ...     ...
    """
    return case(data, context_frame=sys._getframe(2))
