from .class_ import LogosClass


class Subclass(LogosClass):
    _logos_name = "Subclass"

    def __init__(self):
        super().__init__()
        self.superclass = None
        self.protocols = {}
        self.ivars = []
        self._overridden = 1

    @property
    def initRequired(self):
        return 1

    def addProtocol(self, protocol):
        if protocol not in self.protocols:
            self.protocols[protocol] = 0
        self.protocols[protocol] += 1

    def addIvar(self, ivar):
        ivar.class_ = self
        self.ivars.append(ivar)

    def getIvarNamed(self, name):
        for ivar in self.ivars:
            if ivar.name == name:
                return ivar
        return None
