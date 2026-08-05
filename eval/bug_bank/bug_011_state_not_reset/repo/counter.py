class RunningTotal:
    def __init__(self):
        self.total = 0

    def add(self, value):
        self.total += value
        return self.total

    def reset(self):
        pass
