import re
import sys
import importlib


def _to_module_name(name):
    result = re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()
    if result in ('class',):
        result += '_'
    return result


class GeneratorProxy:
    __slots__ = ('_obj', '_generator_cls')

    def __init__(self, generator_cls, obj):
        self._obj = obj
        self._generator_cls = generator_cls

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)
        method = getattr(self._generator_cls, name)
        if self._obj is not None:
            return lambda *args, **kw: method(self._obj, *args, **kw)
        return method


class Generator:
    _generator_package = ""
    _cache = {}

    file_error = None

    @staticmethod
    def for_(obj=None):
        dequalified = None
        cache_key = None

        if obj is not None:
            cache_key = id(obj)
            class_name = getattr(type(obj), '_logos_name', None)
            if class_name is not None:
                dequalified = class_name

        if cache_key is None:
            cache_key = "-"
        if dequalified is None:
            dequalified = "Generator"

        if cache_key in Generator._cache:
            return Generator._cache[cache_key]

        module_name = _to_module_name(dequalified)
        qualified = Generator._generator_package + "." + module_name
        fallback = "Logos.Generator.Base." + module_name

        backend_name = Generator._generator_package.rsplit(".", 1)[-1]

        should_fall_back = False
        try:
            module = importlib.import_module(qualified)
        except (ImportError, ModuleNotFoundError):
            should_fall_back = True
            module = None

        if should_fall_back:
            try:
                module = importlib.import_module(fallback)
                backend_name = "Base"
            except (ImportError, ModuleNotFoundError):
                module = None

        if module is None:
            raise ImportError(
                "Cannot load generator module: tried %s and %s" % (qualified, fallback))

        cls_name = backend_name[0].upper() + backend_name[1:] + dequalified + "Generator"
        generator_cls = getattr(module, cls_name, None)
        if generator_cls is None:
            raise ImportError(
                "Cannot find generator class %s in %s" % (cls_name, module.__name__))

        proxy = GeneratorProxy(generator_cls, obj)
        Generator._cache[cache_key] = proxy
        return proxy

    @staticmethod
    def use(generator_name):
        path = None
        m = re.match(r'^(\w+)@(.+)$', generator_name)
        if m:
            generator_name = m.group(1)
            path = m.group(2)

        if path:
            if path not in sys.path:
                sys.path.insert(0, path)

        Generator._generator_package = "Logos.Generator." + generator_name

        qualified = Generator._generator_package + ".generator"
        try:
            importlib.import_module(qualified)
        except (ImportError, ModuleNotFoundError):
            if Generator.file_error:
                Generator.file_error(-1, "I can't find the %s Generator!" % generator_name)
            else:
                raise ImportError("I can't find the %s Generator!" % generator_name)
