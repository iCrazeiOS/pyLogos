def file_error(lineno, msg):
    raise RuntimeError(msg)


class BaseSubclassGenerator:
    @classmethod
    def declarations(cls, class_obj):
        file_error(-1, "generator does not implement Subclass::declarations")

    @classmethod
    def initializers(cls, class_obj):
        file_error(-1, "generator does not implement Subclass::initializers")

