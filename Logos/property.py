"""Logos::Property - Property data model."""


class Property:
    _logos_name = "Property"

    def __init__(self):
        self.class_ = None
        self.group = None
        self.name = None
        self.type = None
        self.readonly = None
        self.associationPolicy = None
        self.getter = None
        self.setter = None
        self.retainFlag = None
        self.copyFlag = None
        self.nonatomicFlag = None
