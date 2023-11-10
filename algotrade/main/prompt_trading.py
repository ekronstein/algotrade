import random


def prompt_trading(config):
    if config["env"] == "sandbox":
        return True
    if config["env"] == "prod_trade":
        while True:
            inp = input("Enable trading?\n")
            if inp.lower() == "no":
                return False
            if inp.lower() != "yes":
                print("either yes or no, try again\n")
                continue
            while True:
                a, b = random.sample(range(10), 2)
                inp = input(f"what is {a} + {b} ?\n")
                if int(inp) == a + b:
                    return True
                print("wrong, try again\n")
    return False