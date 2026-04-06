from ... import sigil
from ...method import declaration_for_type_with_name, type_encoding_for_arg_type
from ..Base.method import BaseMethodGenerator


class InternalMethodGenerator(BaseMethodGenerator):
    @classmethod
    def originalCallParams(cls, method, customargs=None):
        if method.isNew:
            return ""

        build = "(self, _cmd"
        if customargs is not None and customargs != "":
            build += ", " + customargs
        elif method.numArgs > 0:
            build += ", " + ", ".join(method.argnames)
        build += ")"
        return build

    @classmethod
    def definition(cls, method):
        from .. import Generator
        build = ""
        selftype = cls.selfTypeForMethod(method)
        classref = ""
        cgen = Generator.for_(method.class_)
        if method.scope == "+":
            classref = cgen.superMetaVariable()
        else:
            classref = cgen.superVariable()
        arglist = ""
        for i in range(method.numArgs):
            arglist += ", " + declaration_for_type_with_name(method.argtypes[i], method.argnames[i])
        function_attributes = cls.functionAttributesForMethod(method)
        return_type = cls.returnTypeForMethod(method)
        parameters = "(" + selftype + " __unused self, SEL __unused _cmd" + arglist
        if method.variadic:
            parameters += ", ..."
        parameters += ")"
        build += "static " + declaration_for_type_with_name(return_type, cls.newFunctionName(method) + parameters) + function_attributes
        return build

    @classmethod
    def originalCall(cls, method, customargs=None):
        from .. import Generator
        classargtype = ""
        classref = ""
        cgen = Generator.for_(method.class_)
        if method.scope == "+":
            classargtype = "Class"
            classref = cgen.superMetaVariable()
        else:
            classargtype = method.class_.type
            classref = cgen.superVariable()
        argtypelist = ", ".join(method.argtypes)
        return cls.originalFunctionName(method) + cls.originalCallParams(method, customargs)

    @classmethod
    def declarations(cls, method):
        build = ""
        if not method.isNew:
            selftype = cls.selfTypeForMethod(method)
            function_attributes = cls.functionAttributesForMethod(method)
            build += "static "
            name = ""
            name += function_attributes + "(*" + cls.originalFunctionName(method) + ")(" + selftype + ", SEL"
            argtypelist = ", ".join(method.argtypes)
            if argtypelist:
                name += ", " + argtypelist
            if method.variadic:
                name += ", ..."
            name += ")"
            build += declaration_for_type_with_name(cls.returnTypeForMethod(method), name)
            build += ";"
        return build

    @classmethod
    def initializers(cls, method):
        from .. import Generator
        cgen = Generator.for_(method.class_)
        classvar = cgen.metaVariable() if method.scope == "+" else cgen.variable()
        r = "{ "
        if not method.isNew:
            r += (sigil("register_hook") + "(" + classvar + ", "
                  + cls.selectorRef(method.selector) + ", (IMP)&"
                  + cls.newFunctionName(method) + ", (IMP *)&"
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

