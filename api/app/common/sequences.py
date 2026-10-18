from collections.abc import Sequence


def spread_evenly[T](items: Sequence[T], count: int) -> list[T]:
    if len(items) <= count:
        return list(items)
    return [items[index * len(items) // count] for index in range(count)]


def split_into_batches[T](items: Sequence[T], batch_size: int) -> list[list[T]]:
    return [list(items[start : start + batch_size]) for start in range(0, len(items), batch_size)]
