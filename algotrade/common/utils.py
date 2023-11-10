def calc_fractional_spread(bid: float, ask: float):
    """
    Returns:
        Fraciont of diff between ask and bid prices out of the mid price
    """
    mid = (ask + bid) / 2
    return (ask - bid) / mid


def calc_spread(bid: float, ask: float):
    """
    Returns:
        Fraction of diff between ask and bid prices out of the mid price in basis points
    """
    return 1e4 * calc_fractional_spread(bid, ask)
