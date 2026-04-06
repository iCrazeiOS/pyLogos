from ..Base.function import BaseFunctionGenerator


class LibhookerFunctionGenerator(BaseFunctionGenerator):
    @classmethod
    def initializers(cls, function):
        result = ""
        result += "{" + cls._initExpression(function)
        result += ", (void *)&" + cls.newFunctionName(function)
        result += ", (void **)&" + cls.originalFunctionName(function)
        result += "}"
        return result

