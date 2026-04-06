from ... import sigil


class BaseClassGenerator:
    @classmethod
    def _initExpression(cls, class_obj):
        if class_obj.expression:
            return class_obj.expression
        return 'objc_getClass("' + class_obj.name + '")'

    @classmethod
    def _metaInitExpression(cls, class_obj):
        if class_obj.metaexpression:
            return class_obj.metaexpression
        return "object_getClass(" + cls.variable(class_obj) + ")"

    @classmethod
    def _symbolName(cls, tag, class_obj):
        return sigil(tag, class_obj.group.name, class_obj.name)

    @classmethod
    def variable(cls, class_obj):
        return cls._symbolName("class", class_obj)

    @classmethod
    def metaVariable(cls, class_obj):
        return cls._symbolName("metaclass", class_obj)

    @classmethod
    def declarations(cls, class_obj):
        from .. import Generator
        result = ""
        for method in class_obj.methods:
            result += Generator.for_(method).declarations()
        return result

    @classmethod
    def initializers(cls, class_obj):
        from .. import Generator
        result = ""
        for prop in class_obj.properties:
            result += Generator.for_(prop).initializers()
        for method in class_obj.methods:
            result += Generator.for_(method).initializers()
        return result

