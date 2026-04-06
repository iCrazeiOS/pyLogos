from ... import sigil
from ...util import matched_parenthesis_set, smart_split


def file_error(lineno, msg):
    raise RuntimeError(msg)


class BaseMethodGenerator:
    @classmethod
    def _symbolName(cls, tag, method):
        scope_tag = ("meta_" if method.scope == "+" else "") + tag
        return sigil(scope_tag, method.class_.group.name, method.class_.name, method._new_selector)

    @classmethod
    def originalFunctionName(cls, method):
        return cls._symbolName("orig", method)

    @classmethod
    def newFunctionName(cls, method):
        return cls._symbolName("method", method)

    @classmethod
    def definition(cls, method):
        file_error(-1, "generator does not implement Method::definition")

    @classmethod
    def originalCall(cls, method, customargs=None):
        file_error(-1, "generator does not implement Method::originalCall")

    @classmethod
    def selectorRef(cls, selector):
        if selector == "dealloc":
            return 'sel_registerName("' + selector + '")'
        return "@selector(" + selector + ")"

    @classmethod
    def selfTypeForMethod(cls, method):
        if method.scope == "+":
            return "_LOGOS_SELF_TYPE_NORMAL Class _LOGOS_SELF_CONST"
        if method.methodFamily == "init":
            return "_LOGOS_SELF_TYPE_INIT " + method.class_.type
        return "_LOGOS_SELF_TYPE_NORMAL " + method.class_.type + " _LOGOS_SELF_CONST"

    @classmethod
    def returnTypeForMethod(cls, method):
        if method.methodFamily != "":
            return method.class_.type
        result = method.return_
        if result == "instancetype":
            return method.class_.type
        return result

    @classmethod
    def functionAttributesForMethod(cls, method):
        if method.methodFamily != "":
            return " _LOGOS_RETURN_RETAINED"
        return ""

    @classmethod
    def buildLogCall(cls, method, args):
        from ...method import format_char_for_arg_type, print_arg_for_arg_type

        # Log preamble
        build = 'NSLog(@"' + method.scope + "[<" + method.class_.name + ": %p>"
        argnamelist = ""
        if method.numArgs > 0:
            # For each argument, add its keyword and a format char to the log string.
            for i in range(method.numArgs):
                build += " " + method.selectorParts[i] + ":" + format_char_for_arg_type(method.argtypes[i])[0]
            # This builds a list of args by making sure the format char isn't -- (or, what we're using for non-operational types)
            # Map "format char == -- ? nothing : arg name" over the indices of the arg list.
            newarglist = [print_arg_for_arg_type(method.argtypes[i], method.argnames[i]) for i in range(method.numArgs)]
            existingargs = [a for a in newarglist if a is not None]
            if len(existingargs) > 0:
                argnamelist = ", " + ", ".join(existingargs)
        else:
            # Space and then the only keyword in the selector.
            build += " " + method.selector

        extra_format_specifiers = []
        extra_arguments = []
        for item in smart_split(r'\s*,\s*', args):
            paren_result = matched_parenthesis_set(item)
            type_ = "id"
            if paren_result is not None:
                popen, pclose = paren_result[0], paren_result[1]
                type_ = item[popen:pclose - 1]
            extra_format_specifiers.append(format_char_for_arg_type(type_)[0])
            n = print_arg_for_arg_type(type_, "(" + item + ")")
            if n is not None:
                extra_arguments.append(n)

        # Log postamble
        build += "]"
        if len(extra_format_specifiers) > 0:
            build += ": " + ", ".join(extra_format_specifiers)
        build += '", self' + argnamelist
        if len(extra_arguments) > 0:
            build += ", " + ", ".join(extra_arguments)
        build += ")"
        return build

    @classmethod
    def declarations(cls, method):
        file_error(-1, "generator does not implement Method::declarations")

    @classmethod
    def initializers(cls, method):
        file_error(-1, "generator does not implement Method::initializers")

