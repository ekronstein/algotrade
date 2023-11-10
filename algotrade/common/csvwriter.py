import csv

# from log.log import logger
from loguru import logger


class CSVWriter:
    def __init__(self, writefile: str, fieldnames: list[str], writetrigger=1):
        self.fieldnames = fieldnames
        self.data = {fieldname: [] for fieldname in self.fieldnames}
        self.lines_in_buffer = 0
        self.writefile = writefile
        self.writetrigger = writetrigger
        with open(self.writefile, "w") as csvfile:
            writer = csv.DictWriter(
                csvfile, fieldnames=self.fieldnames, lineterminator="\n"
            )
            writer.writeheader()

    def __enter__(self, *args, **kwargs):
        return self

    def __exit__(self, *args, **kwargs):
        self.dump_data()

    def dump_data(self):
        with open(self.writefile, "a") as csvfile:
            writer = csv.DictWriter(
                csvfile, fieldnames=self.fieldnames, lineterminator="\n"
            )
            for i in range(self.lines_in_buffer):
                writer.writerow({k: v[i] for (k, v) in self.data.items()})
        self.lines_in_buffer = 0
        for v in self.data.values():
            v.clear()

    def add_line(self, line: list):
        if len(line) != len(self.data):
            logger.debug(str(line))
            raise CSVWriter.LineLengthException
        for i, k in enumerate(self.data.keys()):
            self.data[k].append(line[i])
        self.lines_in_buffer += 1
        if self.lines_in_buffer % self.writetrigger == 0:
            self.dump_data()

    class LineLengthException(Exception):
        pass


class LineLengthException(Exception):
    pass
