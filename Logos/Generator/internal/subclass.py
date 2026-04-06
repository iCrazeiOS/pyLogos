from .class_ import InternalClassGenerator


class InternalSubclassGenerator(InternalClassGenerator):
    # declarations is inherited from Class.

    @classmethod
    def _initExpression(cls, class_obj):
        from .. import Generator
        cgen = Generator.for_(class_obj.superclass)
        return ("objc_allocateClassPair(" + cgen.variable() + ", \""
                + class_obj.name + "\", 0)")

    @classmethod
    def initializers(cls, class_obj):
        from .. import Generator
        result = ""
        result += "{ "
        result += super().initializers(class_obj) + " "
        for ivar in class_obj.ivars:
            result += Generator.for_(ivar).initializers()
        result += "objc_registerClassPair(" + cls.variable(class_obj) + "); "
        for protocol in class_obj.protocols:
            result += ("class_addProtocol(" + cls.variable(class_obj)
                       + ", objc_getProtocol(\"" + protocol + "\")); ")
        result += "}"
        return result

