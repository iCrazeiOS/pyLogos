class LogosClass:
    _logos_name = "Class"

    def __init__(self):
        self.name = None
        self._expr = None
        self._metaexpr = None
        self._type = None
        self.hasmetahooks = 0
        self.hasinstancehooks = 0
        self._overridden = 0
        self.required = 0
        self.methods = []
        self.properties = []
        self.group = None

    @property
    def expression(self):
        return self._expr

    @expression.setter
    def expression(self, value):
        self._expr = value
        self._type = "id"
        self._overridden = 1

    @property
    def metaexpression(self):
        return self._metaexpr

    @metaexpression.setter
    def metaexpression(self, value):
        self._metaexpr = value
        self._overridden = 1

    @property
    def type(self):
        return self._type if self._type else self.name + "*"

    @type.setter
    def type(self, value):
        self._type = value

    @property
    def overridden(self):
        return self._overridden

    @property
    def initRequired(self):
        return self.required or len(self.methods) > 0 or len(self.properties) > 0

    def addMethod(self, hook):
        self.methods.append(hook)

    def addProperty(self, prop):
        self.properties.append(prop)
