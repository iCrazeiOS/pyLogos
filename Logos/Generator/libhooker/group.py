from ..Base.group import BaseGroupGenerator


class LibhookerGroupGenerator(BaseGroupGenerator):
    @classmethod
    def initializers(cls, group):
        from .. import Generator
        result = "{"
        for class_obj in group.classes:
            if class_obj.initRequired:
                result += Generator.for_(class_obj).initializers()
        structs = [Generator.for_(func).initializers() for func in group.functions]
        if structs:
            function_count = len(group.functions)
            result += ("LHHookFunctions((struct LHFunctionHook []){"
                       + ",".join(structs) + "}, "
                       + str(function_count) + ");")
        result += "}"
        return result

