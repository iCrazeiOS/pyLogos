from ..Base.function import BaseFunctionGenerator


class MobileSubstrateFunctionGenerator(BaseFunctionGenerator):
    @classmethod
    def initializers(cls, function):
        result = ""
        result += "void * " + cls.variable(function) + " = " + cls._initExpression(function) + ";"
        result += " MSHookFunction((void *)" + cls.variable(function)
        result += ", (void *)&" + cls.newFunctionName(function)
        result += ", (void **)&" + cls.originalFunctionName(function)
        result += ");"
        return result

