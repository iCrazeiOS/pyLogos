import re

from ... import sigil


class BaseGeneratorGenerator:
    @classmethod
    def findPreamble(cls, lines_list):
        for line in (lines_list or []):
            if re.search(r'\s*#\s*(import|include)\s*[<"]logos/logos\.h[">]', line or ''):
                return True
        return False

    @classmethod
    def preamble(cls):
        return ""

    @classmethod
    def staticDeclarations(cls):
        return (
            "#if defined(__clang__)\n"
            "#if __has_feature(objc_arc)\n"
            "#define _LOGOS_SELF_TYPE_NORMAL __unsafe_unretained\n"
            "#define _LOGOS_SELF_TYPE_INIT __attribute__((ns_consumed))\n"
            "#define _LOGOS_SELF_CONST const\n"
            "#define _LOGOS_RETURN_RETAINED __attribute__((ns_returns_retained))\n"
            "#else\n"
            "#define _LOGOS_SELF_TYPE_NORMAL\n"
            "#define _LOGOS_SELF_TYPE_INIT\n"
            "#define _LOGOS_SELF_CONST\n"
            "#define _LOGOS_RETURN_RETAINED\n"
            "#endif\n"
            "#else\n"
            "#define _LOGOS_SELF_TYPE_NORMAL\n"
            "#define _LOGOS_SELF_TYPE_INIT\n"
            "#define _LOGOS_SELF_CONST\n"
            "#define _LOGOS_RETURN_RETAINED\n"
            "#endif\n"
        )

    @classmethod
    def generateClassList(cls, *classnames):
        return "".join("@class " + name + "; " for name in classnames)

    @classmethod
    def classReferenceWithScope(cls, classname, scope):
        prefix = sigil("static_metaclass_lookup" if scope == "+" else "static_class_lookup", classname)
        return prefix + "()"

