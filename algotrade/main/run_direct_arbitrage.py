import asyncio

from loguru import logger

from algotrade.algo.arbitrage.direct_arbitrage import DirectArbitrageFinder
from algotrade.algotrade import AlgoTrade
from algotrade.config import get_config
from algotrade.main.prompt_trading import prompt_trading

info = "logs/{time}_info.log"
debug = "logs/{time}_dbg.log"
logger.add(info, level="INFO")
logger.add(debug, level="DEBUG")

async def main():
    config = get_config()
    algotrade = AlgoTrade(config)
    trading = prompt_trading(config)
    algo = DirectArbitrageFinder(trading, algotrade, config)
    algotrade._get_pubsub()
    await asyncio.gather(
        algotrade.subscribe_handler('quote', algo.on_quote_update),
        algotrade.subscribe_handler('panic', algo.on_panic),
        *algotrade.run()
    )
    

if __name__ == "__main__":
    asyncio.run(main())

