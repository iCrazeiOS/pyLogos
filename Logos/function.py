"""Logos::Function - Function hook data model."""


class Function:
    _logos_name = "Function"

    def __init__(self):
        self.name = None
        self.expression = None
        self.retval = None
        self.args = []
        self.group = None

    def addArg(self, arg):
        self.args.append(arg)
