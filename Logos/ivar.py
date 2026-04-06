"""Logos::Ivar - Instance variable data model."""


class Ivar:
    _logos_name = "Ivar"

    def __init__(self, name=None, type_=None):
        self.name = name
        self.type = type_
        self.class_ = None
