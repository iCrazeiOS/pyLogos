class PatchSourceGenerator:
    def __init__(self, obj, method_name, *args):
        self.object = obj
        self.method = method_name
        self.args = list(args)

    def eval(self):
        from .Generator import Generator
        gen = Generator.for_(self.object)
        method_func = getattr(gen, self.method)
        return method_func(*self.args)
