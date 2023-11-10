from datetime import datetime

import toml

from algotrade.algo.arbitrage.min_ask_max_bid import MinAskMaxBidData
from algotrade.common.csvwriter import CSVWriter
from algotrade.common.utils import calc_spread
from algotrade.config import get_config

config = get_config()
FILE_TIME_FORMAT = config['algos']['direct_arbitrage']["filetimeformat"]
START_TIME = datetime.utcnow()

def get_write_filename(type: str, config: dict,  **kw):
    """
    type: `toml` or `csv`
    """
    sandbox = config['env'] == 'sandbox'
    dev = config['dev']
    threshold = config['algos']['direct_arbitrage']['arbitrage_threshold']
    data_dir = config['algos']['direct_arbitrage']['data_dir']
    return "{}/{}{}/{}_th{}{}.{}".format(
        data_dir,
        "dev/" if sandbox or dev else "",
        type,
        datetime.strftime(START_TIME, FILE_TIME_FORMAT),
        threshold,
        "_sandbox" if sandbox else "",
        'toml' if type == 'configs' else 'csv',
    )


header_fields = [
    "local timestamp",
    "pair",
    "size",
    "min ask market",
    "max bid market",
    "min ask timestamp",
    "max bid timestamp",
    "min ask",
    "max bid",
    "spread bp",
]


def mamb_to_list(mamb: MinAskMaxBidData) -> list:
    return [
        str(datetime.utcnow()),
        str(mamb.get_pair()),
        mamb.size,
        mamb.get_min_ask_market_enum().name.lower(),
        mamb.get_max_bid_market_enum().name.lower(),
        mamb.get_min_ask_quote().timestamp,
        mamb.get_max_bid_quote().timestamp,
        mamb.get_min_ask(),
        mamb.get_max_bid(),
        calc_spread(mamb.get_min_ask(), mamb.get_max_bid()),
    ]


class DirectArbitrageCSVWriter:
    def __init__(self, config):
        self.wrapped_writer = CSVWriter(
            get_write_filename('csv', config), header_fields, 5
        )

    def add_line(self, mamb: MinAskMaxBidData):
        self.wrapped_writer.add_line(mamb_to_list(mamb))

def save_config(config):
    with open(get_write_filename('configs', config), 'w') as f:
        toml.dump(config,f)