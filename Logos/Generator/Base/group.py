class BaseGroupGenerator:
    @classmethod
    def declarations(cls, group):
        from .. import Generator
        result = ""
        for class_obj in group.classes:
            if class_obj.initRequired:
                result += Generator.for_(class_obj).declarations()
        return result

    @classmethod
    def initializers(cls, group):
        from .. import Generator
        result = "{"
        for class_obj in group.classes:
            if class_obj.initRequired:
                result += Generator.for_(class_obj).initializers()
        for func in group.functions:
            result += Generator.for_(func).initializers()
        result += "}"
        return result

