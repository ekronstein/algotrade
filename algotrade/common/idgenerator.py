def id_generator():
    """generates a unique id"""
    _id = 0
    while True:
        yield _id
        _id += 1


gen = id_generator()


def generate_id():
    return next(gen)


if __name__ == "__main__":
    N = 13
    for i in range(N):
        print(generate_id())  # expect printing of 0 trhough N - 1
