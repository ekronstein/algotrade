# About
A library for automatic trading algorithms on multiple markets.
Each algorithm should be implemented as a class implementing the Algorithm protocol.
Events to this object are published by a single Broker object which is also meant to be used directly by the
Algorithm object.

# Getting Started
Add a toml file named secrets.toml to the root directory containing:

[talos]
sandbox = 'xxxx'
prod = 'xxxx'
prod_trade = 'xxxx'

[other_not_yet_supported_market]
sandbox = 'xxxx'
prod = 'xxxx'
prod_trade = 'xxxx'

etc...
.
.
.


# TODO's:
1.  expand tests**
2.  improve error handling**
3.  cleanups**
4.  order rejections handling** - done for now. panic
5.  add time delay since arbitrage to prevent trading on bad data (spikes mainly)**
6.  median filter - this needs a module for data filterring between algo and feeds *
7.  orders manager update orders if more time passed than order's timeout but order is still live **
8.  use as a package for an algo "plugin" class *
9.  new orders timer async *
10. a 'group' parameter on new orders for filtering*
11. better panic handling*
12. improve logging*
13. split TOB quote from Quote to a Quote with size 0
14. handle open order on orders manager upon reconnection 
15. talos user filterring will boost performance 
16. all inline todo's
17. add slots to all dataclasses
18. single crossed exchange error (negative spread is not valid)
19. config validation
20. spread dep aggressiveness (instead of market_order_th)
21. consider running each pair independently... makes more sense until triangulation is implemented
22. add order status back. not just live or not. for logging purposes...
23. improve __init__.py imports 
24. rid of pymitter - Done
25. pubsub add non async handlers support - Done
26. underscore prefix to all non exported - Done


(** high priority)
(* priority)

