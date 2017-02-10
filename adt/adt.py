from collections import OrderedDict
from functools import total_ordering

from toolz import concatv, memoize, identity
import toolz.curried.operator as op


class NamespaceObject:
    __slots__ = '_recursivetype', '_constructortype', '_name', '_constructors'

    def __init__(self, recursivetype, constructortype, name, constructors):
        self._recursivetype = recursivetype
        self._constructortype = constructortype
        self._name = name
        self._constructors = constructors

    def __getitem__(self, types):
        if not isinstance(types, tuple):
            types = types,
        return self._recursivetype(self._name, types)

    def __call__(self, *args, **kwargs):
        return self._constructortype(
            self._constructors,
            self._name,
            *args,
            **kwargs
        )


class RecursiveType:
    __slots__ = '_name', '_types'

    def __init__(self, name, types):
        self._name = name
        self._types = types

    def __repr__(self):
        return '%s[%s]' % (
            self._name,
            ', '.join(map(str, self._types)),
        )


class Constructor:
    __slots__ = '_name', '_args', '_kwargs'

    def __init__(self, constructors, name, *args, **kwargs):
        for k in kwargs:
            if k.startswith('_'):
                raise TypeError(
                    'constructor keyword argument names may not begin with an'
                    ' underscore: %r' % k,
                )

        self._name = name
        self._args = args
        self._kwargs = kwargs
        constructors[name] = self  # register this constructor

    def __repr__(self):
        return '%s(%s%s%s)' % (
            self._name,
            ', '.join(map(str, self._args)),
            ', ' if self._args and self._kwargs else '',
            ', '.join(map(op.mod('%s=%s'), self._kwargs.items())),
        )
    __str__ = __repr__

    __or__ = staticmethod(identity)


@total_ordering
class TypeVar:
    __slots__ = '_name'

    def __init__(self, name):
        self._name = name

    def __repr__(self):
        return self._name
    __str__ = __repr__

    def __le__(self, other):
        return self._name < other._name


def constructor_new(cls, *args, **kwargs):
    if len(args) != len(cls._argtypes):
        raise TypeError(
            '%r takes %d positional arguments but %d were given' % (
                cls.__name__,
                len(cls._argtypes),
                len(args),
            ),
        )

    if kwargs.keys() != cls._kwargtypes.keys():
        raise TypeError(
            'mismatched keyword arguments, expected %r, got: %r' % (
                set(cls._kwargtypes.keys()),
                set(kwargs.keys()),
            ),
        )

    types = cls._types
    for n, (arg, type_) in enumerate(zip(args, cls._argtypes)):
        if isinstance(type_, TypeVar):
            type_ = types[type_]
        if not isinstance(arg, type_):
            raise TypeError(
                'expected type %r for argument at position %d, got %r: %r' % (
                    type_.__name__,
                    n,
                    type(arg).__name__,
                    arg,
                ),
            )

    kwargtypes = cls._kwargtypes
    for k, v in kwargs.items():
        type_ = kwargtypes[k]
        if isinstance(type_, TypeVar):
            type_ = types[type_]
        if not isinstance(v, type_):
            raise TypeError(
                'expected type %r for argument at %r, got %r: %r' % (
                    type_.__name__,
                    k,
                    type(v).__name__,
                    v,
                ),
            )

    self = object.__new__(cls)
    self._args = args
    self._kwargs = kwargs

    for k, v in kwargs.items():
        setattr(self, k, v)

    return self


def constructor_getitem(self, key):
    return self._args[key]


def constructor_repr(self):
    return '%s(%s%s%s)' % (
        type(self),
        ', '.join(map(str, self._args)),
        ', ' if self._args and self._kwargs else '',
        ', '.join(map(op.mod('%s=%s'), self._kwargs.items())),
    )


class _isconstructor:
    """Type trait to mark that a class is a constructor.
    """


@memoize
def adt(base, types):
    _types = OrderedDict(zip(
        sorted(base._typevars.values()),
        types,
    ))
    ADTImpl = type(
        base.__name__,
        (base,),
        {
            '__slots__': ('_args', '_kwargs'),
            '_types': _types,
        },
    )

    for constructor in base._constructors:
        argtypes = list(constructor._args)
        for n, argtype in enumerate(argtypes):
            if (isinstance(argtype, RecursiveType) and
                    argtype._name == base.__name__):
                # recursive structure
                recursive_types = tuple(_types[var] for var in argtype._types)
                argtypes[n] = (
                    ADTImpl
                    if recursive_types == types else
                    base[types]
                )
            else:
                argtypes[n] = argtype
        kwargtypes = dict(constructor._kwargs)
        for k, kwargtype in constructor._kwargs.items():
            if (isinstance(kwargtype, RecursiveType) and
                    kwargtype._name == base.__name__):
                # recursive structure
                recursive_types = tuple(
                    _types[var] for var in kwargtype._types
                )
                kwargtypes[k] = (
                    ADTImpl
                    if recursive_types == types else
                    base[types]
                )
        setattr(
            ADTImpl,
            constructor._name,
            type(
                constructor._name,
                (ADTImpl, _isconstructor),
                {
                    '__new__': constructor_new,
                    '_adt': ADTImpl,
                    '_argtypes': argtypes,
                    '_kwargtypes': kwargtypes,
                    '__getitem__': constructor_getitem,
                    '__repr__': constructor_repr,
                },
            ),
        )
    return ADTImpl


def mk_prepare_structure(RecursiveType, Constructor, TypeVar, valid_arg_names):
    class __prepare__(dict):
        def __init__(self, instance, owner):
            super().__init__()
            self._typevars = {}
            self._constructors = OrderedDict()

        def __getitem__(self, key):
            if key in self._constructors:
                raise ValueError('duplicate constructor: %r' % key)

            if key in self._typevars:
                return self._typevars[key]

            if not key or key in self or key == '__name__':
                return super().__getitem__(key)

            if key[0].isupper():
                return NamespaceObject(
                    RecursiveType,
                    Constructor,
                    key,
                    self._constructors,
                )

            if key not in valid_arg_names:
                return super().__getitem__(key)

            self._typevars[key] = v = TypeVar(key)
            return v

    return __prepare__


class ADTMeta(type):
    def __new__(mcls, name, bases, dict_):
        self = super().__new__(mcls, name, bases, dict_)
        if len(bases) and bases[0] is ADT:
            self._typevars = dict_._typevars
            self._constructors = tuple(dict_._constructors.values())
            constructors = set(self._constructors)
            for constructor in constructors:
                types = concatv(
                    constructor._args,
                    constructor._kwargs.values(),
                )
                for t in types:
                    if isinstance(t, RecursiveType) and t._name != name:
                        raise TypeError(
                            'recursive type name must be the same as the type'
                            ' name, %r != %r' % (
                                t._name,
                                name,
                            ),
                        )
                    if t in constructors:
                        raise TypeError(
                            'constructor %r has arguments that are other'
                            ' constructors' % constructor,
                        )
            if not self._typevars:
                return adt(self, ())
        return self

    __prepare__ = mk_prepare_structure(
        RecursiveType,
        Constructor,
        TypeVar,
        frozenset({'_%d' % (n + 1) for n in range(255)}),
    )

    def __getitem__(self, types):
        if not isinstance(types, tuple):
            types = types,

        if len(types) != len(self._typevars):
            raise TypeError(
                'expected %d types, got %d: %r' % (
                    len(self._typevars),
                    len(types),
                    types,
                ),
            )
        return adt(self, types)

    def __repr__(self):
        base = self.__name__
        if not hasattr(self, '_types'):
            return base

        if issubclass(self, _isconstructor):
            return '.'.join((repr(self._adt), self.__name__))

        if not self._types:
            return str(base)

        return '%s[%s]' % (
            base,
            ', '.join(t.__name__ for t in self._types.values()),
        )


class ADT(metaclass=ADTMeta):
    def __new__(cls, *args):
        if cls is ADT:
            raise TypeError('Cannot create instances of %r' % cls.__name__)
        raise TypeError(
            '%r is an ADT which can only be instantiated through constructors:'
            ' %r' % (
                cls.__name__,
                cls._constructors,
            ),
        )
