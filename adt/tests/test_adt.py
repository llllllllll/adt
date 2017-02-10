import pytest

from adt import ADT, match, case


class List(ADT):
    Nil()
    Cons(_1, List[_1])


def test_direct_construction_fails_recurisive():
    with pytest.raises(TypeError) as e:
        List(1)

    assert str(e.value) == (
        "'List' is an ADT which can only be instantiated through"
        " constructors: (Nil(), Cons(_1, List[_1]))"
    )


def test_list():
    ls = List[int].Cons(1, List[int].Cons(2, List[int].Nil()))

    @match(ls)
    class matched(case):
        Nil() >> None
        Cons(head, tail) >> (head, tail)

    head, tail = matched
    assert head == 1

    @match(tail)
    class matched(case):
        Nil() >> None
        Cons(head, tail) >> (head, tail)

    head, tail = matched
    assert head == 2

    @match(tail)
    class matched(case):
        Nil() >> None
        Cons(head, tail) >> (head, tail)

    assert matched is None


class Either(ADT):
    Left(_1)
    Right(_2)


def test_direct_construction_fails():
    with pytest.raises(TypeError) as e:
        Either(1)

    assert str(e.value) == (
        "'Either' is an ADT which can only be instantiated through"
        " constructors: (Left(_1), Right(_2))"
    )
