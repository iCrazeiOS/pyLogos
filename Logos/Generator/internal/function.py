from ..Base.function import BaseFunctionGenerator


class InternalFunctionGenerator(BaseFunctionGenerator):
    @classmethod
    def initializers(cls, function):
        return " /* internal::Function does not implement initializers */;"

