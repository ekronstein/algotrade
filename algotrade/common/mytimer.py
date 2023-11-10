import time


def timer(func):
    def wrapper(*args, **kw):
        ti = time.time_ns()
        res = func(*args, **kw)
        te = time.time_ns()
        print(
            "function {} in file {} ran in {} seconds".format(
                func.__name__, __file__, (te - ti) / 1e9
            )
        )
        return res

    return wrapper
