import pytest

from app.common.sequences import split_into_batches, spread_evenly


@pytest.fixture(
    params=[
        ([1, 2, 3, 4], 2, [1, 3]),
        ([1, 2, 3, 4, 5, 6, 7], 3, [1, 3, 5]),
        ([1, 2], 5, [1, 2]),
        ([], 3, []),
    ]
)
def spread_items(request):
    items, count, expected = request.param
    return spread_evenly(items, count), expected


@pytest.fixture(
    params=[
        ([1, 2, 3, 4, 5], 2, [[1, 2], [3, 4], [5]]),
        ([1, 2], 5, [[1, 2]]),
        ([], 3, []),
    ]
)
def batches(request):
    items, batch_size, expected = request.param
    return split_into_batches(items, batch_size), expected


def test_spread_evenly_keeps_count_items_across_the_whole_list(spread_items):
    actual, expected = spread_items
    assert actual == expected


def test_split_into_batches_keeps_the_order_and_a_short_last_batch(batches):
    actual, expected = batches
    assert actual == expected
