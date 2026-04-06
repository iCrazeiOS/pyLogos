import re

from ..Base.generator import BaseGeneratorGenerator


class LibhookerGeneratorGenerator(BaseGeneratorGenerator):
    @classmethod
    def findPreamble(cls, lines_list):
        has_libhooker = False
        for line in (lines_list or []):
            if re.search(r'(#|@)(import|include)\s*(<|)libhooker', line or ''):
                has_libhooker = True
                break
        return super().findPreamble(lines_list) and has_libhooker

    @classmethod
    def preamble(cls, skipIncludes=False):
        if skipIncludes:
            return super().preamble()
        else:
            return "\n".join([
                super().preamble(),
                "#import <libhooker/libblackjack.h>",
                "#import <objc/runtime.h>"
            ])

    @classmethod
    def staticDeclarations(cls):
        return "\n".join([
            super().staticDeclarations(),
            '__asm__(".linker_option \\"-lhooker\\"");',
            '__asm__(".linker_option \\"-lblackjack\\"");',
            ""
        ])

