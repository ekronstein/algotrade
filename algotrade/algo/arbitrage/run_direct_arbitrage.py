import asyncio
import random

from colorama import Fore
from config import _config
from loguru import logger
from pymitter import EventEmitter

import algotrade.connect.adapter.adapter as msg
from algotrade.algo.arbitrage.direct_arbitrage import DirectArbitrageFinder
from algotrade.algo.arbitrage.direct_arbitrage_data_writer import \
    DirectArbitrageCSVWriter
from algotrade.common.event_topics import Topic
from algotrade.connect.adapter import talos
from algotrade.connect.connector.connector import Connector
from algotrade.orders_manager import OrdersManager
from algotrade.pnl_monitor import PnLMonitor

info = "logs/{time}_info.log"
debug = "logs/{time}_dbg.log"
logger.add(info, level="INFO")
logger.add(debug, level="DEBUG")


def prompt_trading(config):
    if config["env"] == "sandbox":
        return True
    if config["env"] == "prod_trade":
        while True:
            inp = input("Enable trading?\n")
            if inp == "no":
                return False
            if inp != "yes":
                print("either yes or no, try again\n")
                continue
            while True:
                a, b = random.sample(range(10), 2)
                inp = input(f"what is {a} + {b} ?\n")
                if int(inp) == a + b:
                    return True
                print("wrong, try again\n")
    return False


async def main():
    is_sandbox = _config["env"] == "sandbox"
    trading = prompt_trading(_config)
    emitter = EventEmitter()
    connector = Connector(
        talos.get_uri(is_sandbox),
        talos.TalosHeadersGenerator(is_sandbox),
        emitter,
    )  # connector to Talos
    talos: msg.Adapter = talos.TalosAdapter(
        emitter, pairs=_config["pairs"], sizes=_config["sizes"], trading=trading
    )
    orders_manager = OrdersManager(emitter)
    pnl_monitor = PnLMonitor(emitter, orders_manager)
    algo = DirectArbitrageFinder(emitter, orders_manager, trading=trading)
    arbitrage_writer = DirectArbitrageCSVWriter(
        is_sandbox, _config["arbitrage_threshold"], _config["dev"]
    )

    # Subscribing to topics:
    emitter.on(Topic.ORDER_UPDATE_IN.name, orders_manager.on_order_update)
    emitter.on(Topic.QUOTE_UPDATE_IN.name, algo.on_quote_update)
    emitter.on(Topic.PAYLOAD_RECV_IN.name, talos.on_payload_recv_in)
    emitter.on(Topic.PAYLOAD_OUT.name, connector.send)
    emitter.on(Topic.CONNECTION_ESTABLISHED.name, talos.on_connection_established)
    emitter.on(Topic.ORDERS_OUT.name, talos.on_orders_out)
    emitter.on(Topic.ORDERS_OUT.name, orders_manager.on_orders_out)

    emitter.on(Topic.PANIC.name, talos.on_panic)  # panic means stop trading basically
    emitter.on(Topic.PANIC.name, lambda msg: print(Fore.RED + msg + Fore.RESET))
    emitter.on(Topic.CANCEL_ORDERS_OUT.name, talos.on_cancel_orders_out)

    emitter.on(Topic.TRADE_IN.name, orders_manager.on_trade_in)
    emitter.on(Topic.TRADE_IN.name, pnl_monitor.on_trade_in)


    await connector.connect()


if __name__ == "__main__":
    asyncio.run(main())
