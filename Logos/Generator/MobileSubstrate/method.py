from ...method import declaration_for_type_with_name, type_encoding_for_arg_type
from ..Base.method import BaseMethodGenerator


class MobileSubstrateMethodGenerator(BaseMethodGenerator):
    @classmethod
    def _originalMethodPointerDeclaration(cls, method):
        if not method.isNew:
            build = "static "
            classargtype = cls.selfTypeForMethod(method)
            name = "(*" + cls.originalFunctionName(method) + ")(" + classargtype + ", SEL"
            argtypelist = ", ".join(method.argtypes)
            if argtypelist:
                name += ", " + argtypelist
            if method.variadic:
                name += ", ..."
            name += ")"
            build += declaration_for_type_with_name(cls.returnTypeForMethod(method), name)
            build += cls.functionAttributesForMethod(method)
            return build
        return None

    @classmethod
    def _methodPrototype(cls, method, includeArgNames=False):
        build = "static "
        classargtype = cls.selfTypeForMethod(method)
        arglist = ""
        if includeArgNames:
            for i in range(method.numArgs):
                arglist += ", " + declaration_for_type_with_name(method.argtypes[i], method.argnames[i])
        else:
            typelist = ", ".join(method.argtypes)
            if typelist:
                arglist = ", " + typelist

        name = (cls.newFunctionName(method) + "(" + classargtype
                + (" __unused self" if includeArgNames else "")
                + ", SEL"
                + (" __unused _cmd" if includeArgNames else "")
                + arglist)
        if method.variadic:
            name += ", ..."
        name += ")"
        build += declaration_for_type_with_name(cls.returnTypeForMethod(method), name)
        build += cls.functionAttributesForMethod(method)
        return build

    @classmethod
    def definition(cls, method):
        build = ""
        build += cls._methodPrototype(method, True)
        return build

    @classmethod
    def originalCall(cls, method, customargs=None):
        if method.isNew:
            return ""

        build = cls.originalFunctionName(method) + "(self, _cmd"
        if customargs is not None and customargs != "":
            build += ", " + customargs
        elif method.numArgs > 0:
            build += ", " + ", ".join(method.argnames)
        build += ")"
        return build

    @classmethod
    def declarations(cls, method):
        build = ""
        orig = cls._originalMethodPointerDeclaration(method)
        if orig is not None:
            build += orig + "; "
        build += cls._methodPrototype(method) + "; "
        return build

    @classmethod
    def initializers(cls, method):
        from .. import Generator
        cgen = Generator.for_(method.class_)
        classvar = cgen.metaVariable() if method.scope == "+" else cgen.variable()
        r = "{ "
        if not method.isNew:
            r += ("MSHookMessageEx(" + classvar + ", "
                  + cls.selectorRef(method.selector) + ", (IMP)&"
                  + cls.newFunctionName(method) + ", (IMP*)&"
                  + cls.originalFunctionName(method) + ");")
        else:
            if not method.type:
                r += "char _typeEncoding[1024]; unsigned int i = 0; "
                types_to_encode = [method.return_, "id", "SEL"] + list(method.argtypes)
                for t in types_to_encode:
                    type_encoding = type_encoding_for_arg_type(t)
                    if type_encoding is not None:
                        type_encoding_bits = list(type_encoding)
                        for idx, char in enumerate(type_encoding_bits):
                            offset_str = "i" + (" + " + str(idx) if idx > 0 else "")
                            r += "_typeEncoding[" + offset_str + "] = '" + char + "'; "
                        r += "i += " + str(len(type_encoding_bits)) + "; "
                    else:
                        r += ("memcpy(_typeEncoding + i, @encode(" + t
                              + "), strlen(@encode(" + t + "))); i += strlen(@encode("
                              + t + ")); ")
                r += "_typeEncoding[i] = '\\0'; "
            else:
                r += 'const char *_typeEncoding = "' + method.type + '"; '
            r += ("class_addMethod(" + classvar + ", "
                  + cls.selectorRef(method.selector) + ", (IMP)&"
                  + cls.newFunctionName(method) + ", _typeEncoding); ")
        r += "}"
        return r

