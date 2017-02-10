from adt import ADT, case, match


class Either(ADT):
    Left(_1)
    Right(_2)


@print
@match(Either[int, float].Left(1))
class _(case):
    Right(_1) >> float('nan')
    Left(_1) >> _1 + 1


class Struct(ADT):
    A(a=_1, b=_1)
    B(a=_2, b=_2)


@print
@match(Struct[int, float].A(a=1, b=2))
class _(case):
    A(a=_1, b=_2) >> _1 + _2
    B(a=_1, b=_2) >> _1 - _2


class List(ADT):
    Nil()
    Cons(_1, List[_1])



@match(List[int].Cons(1, List[int].Nil()))
class _(case):
    Nil() >> print('empty')  # note: not printed
    Cons(_1, _2) >> print('not empty')
