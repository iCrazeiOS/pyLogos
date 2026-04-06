from ... import sigil
from ...util import matched_parenthesis_set


def file_error(lineno, msg):
    raise RuntimeError(msg)


class BaseFunctionGenerator:
    @classmethod
    def _initExpression(cls, function):
        if function.expression:
            return function.expression
        return "(void *)" + function.name

    @classmethod
    def _symbolName(cls, tag, function):
        return sigil(tag, function.group.name, function.name)

    @classmethod
    def variable(cls, function):
        return cls._symbolName("symbol", function)

    @classmethod
    def originalFunctionName(cls, function):
        return cls._symbolName("orig", function)

    @classmethod
    def newFunctionName(cls, function):
        return cls._symbolName("function", function)

    @classmethod
    def originalFunctionCall(cls, function, args=None):
        result = cls.originalFunctionName(function) + "("
        if not args and (not function.args or function.args[0] != "void"):
            arg_names = [cls.getArgumentName(a) for a in function.args]
            result += ", ".join(arg_names)
        elif args is not None:
            result += args
        result += ")"
        return result

    @classmethod
    def declaration(cls, function):
        result = ""
        result += "__unused static " + function.retval + " (*" + cls.originalFunctionName(function) + ")(" + ", ".join(function.args) + "); "
        result += "__unused static " + function.retval + " " + cls.newFunctionName(function) + "(" + ", ".join(function.args) + ")"
        return result

    @classmethod
    def initializers(cls, function):
        file_error(-1, "Base::Function does not implement initializers")

    ##########
    # extras #
    ##########

    @classmethod
    def getArgumentName(cls, arg):
        # Split the argument string by spaces
        arg_array = cls.notSoSmartSplit(arg, " ")
        # Try to get the name of the last element of the array if it is a function pointer
        result = cls.escapeFunctionPointer(arg_array[-1])
        # Separate the name from trailing vector size
        result = result.replace("[", " [")
        # Trim spaces or asterisks from the start
        while len(result) > 0 and (result[0] == " " or result[0] == "*"):
            result = result[1:]
        # Split the resulting string by spaces
        arg_array = cls.notSoSmartSplit(result, " ")
        # Get the first element
        result = arg_array[0]
        return result

    @classmethod
    def escapeFunctionPointer(cls, arg):
        import re
        if not re.search(r'\(\s*[*^]', arg):
            return arg
        substring = arg
        paren_result = matched_parenthesis_set(substring, False)
        if paren_result is None:
            return arg
        opening, closing = paren_result[0], paren_result[1]
        offset = 0
        while True:
            # We want to put the parameter name right before the closing ) in the deepest nested set if we found a (^ or (*.
            substring = substring[opening:closing - 1]
            offset += opening
            new_result = matched_parenthesis_set(substring, False)
            if new_result is None:
                break
            opening = new_result[0]
            closing = new_result[1]
        return arg[offset:offset + closing - opening - 1]

    # for a lack of Logos::Util::matchedDelimiterSet()
    @classmethod
    def notSoSmartSplit(cls, argument_string, delimiter=None):
        if not delimiter:
            delimiter = ","
        argument_string += delimiter  # uber hax

        # curved  brackets or parens ()
        parens_level = 0
        # squared brackets or crotchets []
        crotchets_level = 0
        # curly   brackets or braces {}
        braces_level = 0
        # angled  brackets or chevrons <>
        chevrons_level = 0

        token = ""
        pc = ""

        args = []

        for c in argument_string:
            if c == delimiter:
                # If at root level, end token, push to array and start again
                if parens_level == 0 and crotchets_level == 0 and braces_level == 0 and chevrons_level == 0:
                    args.append(token)
                    pc = c
                    token = ""
                    continue

            if c == "(":
                parens_level += 1
            if c == ")":
                parens_level -= 1

            if c == "[":
                crotchets_level += 1
            if c == "]":
                crotchets_level -= 1

            if c == "{":
                braces_level += 1
            if c == "}":
                braces_level -= 1

            if c == "<":
                chevrons_level += 1
            if c == ">":
                chevrons_level -= 1

            # skip redundant empty spaces
            if (pc == delimiter and c == " ") or (pc == " " and c == " "):
                continue

            # Concatenate char to token
            token += c
            # save previous char
            pc = c

        return args

