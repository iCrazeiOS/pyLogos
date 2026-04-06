from .class_ import LogosClass
from .function import Function


class Group:
    _logos_name = "Group"

    def __init__(self):
        self.name = None
        self.explicit = 1
        self.initialized = 0
        self.initLine = -1
        self.classes = []
        self.functions = []

    @property
    def initRequired(self):
        for cls in self.classes:
            if cls.initRequired:
                return 1
        if len(self.functions) > 0:
            return 1
        return 0

    def addClass(self, cls):
        cls.group = self
        self.classes.append(cls)

    def addClassNamed(self, name):
        cls = self.getClassNamed(name)
        if cls is not None:
            return cls

        cls = LogosClass()
        cls.name = name
        self.addClass(cls)
        return cls

    def getClassNamed(self, name):
        for cls in self.classes:
            if cls.name == name:
                return cls
        return None

    def addFunction(self, args):
        args = list(args)
        function_retval = args.pop(0)
        function_name = args.pop(0)
        function_args = args

        function = Function()
        function.retval = function_retval
        function.name = function_name
        for arg in function_args:
            function.addArg(arg)
        function.group = self
        self.functions.append(function)

        return function

    def getFunctionNamed(self, name):
        for func in self.functions:
            if func.name == name:
                return func
        return None
