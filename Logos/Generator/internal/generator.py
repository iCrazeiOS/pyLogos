import re

from ... import sigil
from ..Base.generator import BaseGeneratorGenerator


class InternalGeneratorGenerator(BaseGeneratorGenerator):
    @classmethod
    def findPreamble(cls, lines_list):
        has_objc_message = False
        for line in (lines_list or []):
            if re.search(r'\s*#\s*(import|include)\s*[<"]objc/message\.h[">]', line or ''):
                has_objc_message = True
                break
        return super().findPreamble(lines_list) and has_objc_message

    @classmethod
    def preamble(cls):
        return "\n".join([
            super().preamble(),
            "#include <objc/message.h>"
        ])

    @classmethod
    def staticDeclarations(cls):
        return "\n".join([
            super().staticDeclarations(),
            "__attribute__((unused)) static void " + sigil("register_hook") + "(Class _class, SEL _cmd, IMP _new, IMP *_old) {",
            "unsigned int _count, _i;",
            "Class _searchedClass = _class;",
            "Method *_methods;",
            "while (_searchedClass) {",
            "_methods = class_copyMethodList(_searchedClass, &_count);",
            "for (_i = 0; _i < _count; _i++) {",
            "if (method_getName(_methods[_i]) == _cmd) {",
            "if (_class == _searchedClass) {",
            "*_old = method_setImplementation(_methods[_i], _new);",
            "} else {",
            "*_old = method_getImplementation(_methods[_i]);",
            "class_addMethod(_class, _cmd, _new, method_getTypeEncoding(_methods[_i]));",
            "}",
            "free(_methods);",
            "return;",
            "}",
            "}",
            "free(_methods);",
            "_searchedClass = class_getSuperclass(_searchedClass);",
            "}",
            "}"
        ])

