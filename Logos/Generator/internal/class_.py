from ... import sigil
from ..Base.class_ import BaseClassGenerator


class InternalClassGenerator(BaseClassGenerator):
    @classmethod
    def superVariable(cls, class_obj):
        return sigil("superclass", class_obj.group.name, class_obj.name)

    @classmethod
    def superMetaVariable(cls, class_obj):
        return sigil("supermetaclass", class_obj.group.name, class_obj.name)

    @classmethod
    def declarations(cls, class_obj):
        result = ""
        if class_obj.hasinstancehooks:
            result += "static Class " + cls.superVariable(class_obj) + "; "
        if class_obj.hasmetahooks:
            result += "static Class " + cls.superMetaVariable(class_obj) + "; "
        result += super().declarations(class_obj)
        return result

    @classmethod
    def initializers(cls, class_obj):
        result = ""
        if class_obj.required or class_obj.overridden or class_obj.hasinstancehooks or class_obj.hasmetahooks:
            result += "Class " + cls.variable(class_obj) + " = " + cls._initExpression(class_obj) + "; "
        if class_obj.hasmetahooks:
            result += "Class " + cls.metaVariable(class_obj) + " = " + cls._metaInitExpression(class_obj) + "; "
        if class_obj.hasinstancehooks:
            result += cls.superVariable(class_obj) + " = class_getSuperclass(" + cls.variable(class_obj) + "); "
        if class_obj.hasmetahooks:
            result += cls.superMetaVariable(class_obj) + " = class_getSuperclass(" + cls.metaVariable(class_obj) + "); "
        result += super().initializers(class_obj)
        return result

