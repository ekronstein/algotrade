import pytest

from algotrade.common.enums import Side
from algotrade.order_book.order_book import L2OrderBook, diff


@pytest.fixture()
def book():
    book = L2OrderBook()
    book.update(bids={1:1, 1.1:1, 1.2:0.1}, asks={1.3:0.1, 1.4:1, 1.5:1})
    yield book

def test_remove_level(book):
    book.update(bids={1:0}, asks={})
    assert 1 not in book._levels[Side.BUY], "zero size update for level 1, but level still in book"
    assert book.get_size(Side.BUY, 1) == 0, "size at price level 1 on buy side should be considered 0"
    assert 1.1 in book._levels[Side.BUY], "1.1 not in book but it was in it and should not have been updated at all"
    assert book.get_size(Side.BUY, 1.1) == 1, "size at price level 1 on buy side should be 0"
    assert book.get_tob(Side.BUY) == (1.2, 0.1), "TOB should not have been changed"
    
def test_tob(book):
    book.update(bids={1.2: 0}, asks={1.3:0})
    assert book.get_tob(Side.BUY) == (1.1, 1), "TOB buy level removed but new TOB buy is wrong"
    assert book.get_tob(Side.SELL) == (1.4, 1), "TOB sell level removed but new TOB sell is wrong"
    book.update(bids={1.2:0.2}, asks={1.3:0.2})
    assert book.get_tob(Side.BUY) == (1.2, 0.2), "TOB buy level surpassed but new TOB buy is wrong"
    assert book.get_tob(Side.SELL) == (1.3, 0.2), "TOB sell level surpassed but new TOB sell is wrong"

def test_get_level(book):
    assert book.get_level(Side.BUY, nth_from_top=2) == (1.1, 1), "get_level for 2nd level from TOB got wrong results"
    assert book.get_level(Side.SELL, nth_from_top=2) == (1.4, 1), "get_level for 2nd level from TOB got wrong results"

def test_delta_update(book):
    deltas = {'bid_deltas':{1:-1, 1.1:-0.5, 1.2:-0.1}, 'ask_deltas':{1.6:1}}
    book.delta_update(**deltas)
    assert book.get_level(side=Side.SELL, nth_from_top=4) == (1.6, 1), "a new level added but not reflected in the book"
    assert book.get_tob(Side.BUY) == (1.1, 0.5), "TOB after change is incorrect"
    nleft = len(book._levels[Side.BUY])
    assert nleft == 1, f"expected one left level on buy side, but have {nleft}"
    with pytest.raises(ValueError) as e_info:
        book.delta_update(bid_deltas={1.1:-0.6}, ask_deltas={})

def test_negative_size(book):
    with pytest.raises(ValueError) as e_info:
        book.update(bids={1:-1}, asks={})

def test_negatives(book):
    with pytest.raises(ValueError) as e_info:
        book.update(bids={-1:1}, asks={})
    with pytest.raises(ValueError) as e_info:
        book.update(bids={-1:-1}, asks={})

def test_diff():
    book1 = L2OrderBook()
    book1.update(bids={1:1, 1.1:1, 1.2:0.1}, asks={1.3:0.1, 1.4:1, 1.5:1})
    book2 = L2OrderBook()
    book2.update(bids={1:1}, asks={1.3:0.1})
    assert 1 in book1.bids()
    assert 1.3 in book1.asks()
    d = diff(book1, book2)
    assert 1 not in d.bids()
    assert 1.3 not in d.asks()

def test_has_tob():
    book = L2OrderBook()
    book.update(asks={1:1})
    assert not book.has_tob(Side.BUY)
    assert book.has_tob(Side.SELL)
    book.update(bids={1:1})
    assert book.has_tob(Side.BUY)