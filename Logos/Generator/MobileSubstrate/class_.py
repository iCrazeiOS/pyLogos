from ..Base.class_ import BaseClassGenerator


class MobileSubstrateClassGenerator(BaseClassGenerator):
    @classmethod
    def initializers(cls, class_obj):
        result = ""
        if class_obj.required or class_obj.overridden or class_obj.hasinstancehooks or class_obj.hasmetahooks:
            result += "Class " + cls.variable(class_obj) + " = " + cls._initExpression(class_obj) + "; "
        if class_obj.hasmetahooks:
            result += "Class " + cls.metaVariable(class_obj) + " = " + cls._metaInitExpression(class_obj) + "; "
        result += super().initializers(class_obj)
        return result

