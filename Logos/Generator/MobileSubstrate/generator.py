import re

from ..Base.generator import BaseGeneratorGenerator


class MobileSubstrateGeneratorGenerator(BaseGeneratorGenerator):
    @classmethod
    def findPreamble(cls, lines_list):
        has_substrate = False
        for line in (lines_list or []):
            if re.search(r'\s*#\s*(import|include)\s*[<"]substrate\.h[">]', line or ''):
                has_substrate = True
                break
        return super().findPreamble(lines_list) and has_substrate

    @classmethod
    def preamble(cls, skipIncludes=False):
        if skipIncludes:
            return super().preamble()
        else:
            return "\n".join([super().preamble(), "#include <substrate.h>"])

    @classmethod
    def staticDeclarations(cls):
        return "\n".join([
            super().staticDeclarations(),
            '__asm__(".linker_option \\"-framework\\", \\"CydiaSubstrate\\"");',
            ""
        ])

