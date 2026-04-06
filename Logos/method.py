import re
from .util import matched_parenthesis_set

# --- Pre-compiled regex patterns ---

# Integral type matching
_RE_INTEGRAL = re.compile(
    r'^((signed|unsigned)\s+)?(unsigned|signed|int|long|long\s+long|bool|BOOL|_Bool|char|short)$'
)
_RE_UNSIGNED = re.compile(r'\bunsigned\b')
_RE_INT_WORD = re.compile(r'\bint\b')
_RE_LONG_WORD = re.compile(r'\blong\b')
_RE_LONG_LONG_WORD = re.compile(r'\blong long\b')
_RE_SHORT_WORD = re.compile(r'\bshort\b')
_RE_CHAR_WORD = re.compile(r'\bchar\b')

# NS/GS type matching
_RE_NS_LONG_TYPES = re.compile(
    r'^NS(Integer|SocketNativeHandle|StringEncoding|SortOptions|ComparisonResult|'
    r'EnumerationOptions|(Hash|Map)TableOptions|SearchPath(Directory|DomainMask))$',
    re.IGNORECASE,
)
_RE_NS_UINTEGER = re.compile(r'^NSUInteger$', re.IGNORECASE)
_RE_GS_FONT = re.compile(r'^GS(FontTraitMask)$', re.IGNORECASE)

# Pointer type matching
_RE_CHAR_PTR = re.compile(r'^char\s*\*$')
_RE_VOID_PTR = re.compile(r'^void\s*\*$')
_RE_ID_PTR = re.compile(r'^id\s*\*$')
_RE_NUMERIC_PTR = re.compile(
    r'^((unsigned|signed)\s+)?(unsigned|signed|int|long|long\s+long|'
    r'bool|BOOL|_Bool|char|short|float|double)\s*\*+$'
)
_RE_NS_PTR_ARRAY = re.compile(r'^NS.*?(Pointer|Array)$')
_RE_NSZONE_PTR = re.compile(r'^NSZone\s*\*$')
_RE_STRUCT_PTR = re.compile(r'^struct.*\*$')
_RE_MULTI_PTR = re.compile(r'\*\*+$')
_RE_ARRAY_SUB = re.compile(r'\[.*\]$')

# Object/block types
_RE_BLOCK = re.compile(r'\(\^\)')
_RE_WORD_PTR = re.compile(r'^\w+\s*\*$')
_RE_WORD_REF = re.compile(r'^\w+Ref$')

# Discarded types
_RE_CG_CF_VOID = re.compile(r'^(CG\w*|CF\w*|void)$')
_NS_HASH_MAP_TYPES = frozenset({
    'NSHashTable', 'NSHashTableCallbacks',
    'NSMapTable', 'NSMapTableKeyCallbacks', 'NSMapTableValueCallbacks',
    'NSMapEnumerator',
})

# Type encoding
_RE_UNSIGNED_CHAR = re.compile(r'^unsigned\s+char$')
_RE_UNSIGNED_INT = re.compile(r'^unsigned\s+int$')
_RE_UNSIGNED_SHORT = re.compile(r'^unsigned\s+short$')
_RE_UNSIGNED_LONG = re.compile(r'^unsigned\s+long$')
_RE_UNSIGNED_LONG_LONG = re.compile(r'^unsigned\s+long long$')
_RE_BASE_PTR = re.compile(r'^([^*\s]+)\s*\*$')

# Declaration parsing
_RE_FUNC_PTR_DECL = re.compile(r'\(\s*[*^]')

# Method family
_RE_ALLOC_FAMILY = re.compile(r'^alloc($|[A-Z,:])')
_RE_INIT_FAMILY = re.compile(r'^init($|[A-Z,:])')

# Floating-point type names
_FLOAT_TYPES = frozenset({'double', 'float', 'CGFloat', 'CGDouble', 'NSTimeInterval'})


class Method:
    _logos_name = "Method"

    def __init__(self):
        self.class_ = None
        self.scope = None
        self.return_ = None
        self.selectorParts = []
        self.argnames = []
        self.argtypes = []
        self._new = 0
        self.type = ""
        self.variadic = 0

    @property
    def isNew(self):
        return self._new

    def setNew(self, value):
        self._new = value

    @property
    def numArgs(self):
        return len(self.argtypes)

    def addArgument(self, type_, name):
        self.argtypes.append(type_)
        self.argnames.append(name)

    @property
    def selector(self):
        if self.numArgs == 0:
            return self.selectorParts[0]
        return ":".join(self.selectorParts) + ":"

    @property
    def _new_selector(self):
        if self.numArgs == 0:
            return self.selectorParts[0]
        return "$".join(self.selectorParts) + "$"

    @property
    def methodFamily(self):
        sel = self.selector
        if self.scope == "+":
            if _RE_ALLOC_FAMILY.match(sel):
                if self.return_ in ("id", "instancetype"):
                    return "alloc"
            if sel == "new":
                if self.return_ in ("id", "instancetype"):
                    return "new"
        else:
            if _RE_INIT_FAMILY.match(sel):
                if self.return_ in ("id", "instancetype"):
                    return "init"
            if sel in ("copy", "copyWithZone:"):
                return "copy"
            if sel in ("mutableCopy", "mutableCopyWithZone:"):
                return "mutableCopy"
        return ""


def format_char_for_arg_type(argtype):
    s = argtype.strip()

    # Straight char gets '%c'
    if s == 'char':
        return ("'%c'", False)

    # Integral types with optional signed/unsigned prefix
    if _RE_INTEGRAL.match(s):
        conversion = "u" if _RE_UNSIGNED.search(s) else "d"

        length = ""
        if _RE_INT_WORD.search(s):
            length = ""
        if _RE_LONG_WORD.search(s):
            length = "l"
        if _RE_LONG_LONG_WORD.search(s):
            length = "ll"
        if _RE_SHORT_WORD.search(s):
            length = "h"
        if _RE_CHAR_WORD.search(s):
            length = "hh"

        return ("%" + length + conversion, False)

    if _RE_NS_LONG_TYPES.match(s):
        return ("%ld", False)
    if _RE_NS_UINTEGER.match(s):
        return ("%lu", False)
    if _RE_GS_FONT.match(s):
        return ("%d", False)

    # Pointer types
    if _RE_CHAR_PTR.match(s):
        return ("%s", False)
    if _RE_VOID_PTR.match(s):
        return ("%p", False)
    if _RE_ID_PTR.match(s):
        return ("%p", False)
    if _RE_NUMERIC_PTR.match(s):
        return ("%p", False)
    if _RE_NS_PTR_ARRAY.match(s):
        return ("%p", False)
    if _RE_NSZONE_PTR.match(s):
        return ("%p", False)
    if _RE_STRUCT_PTR.search(s):
        return ("%p", False)
    if _RE_MULTI_PTR.search(s):
        return ("%p", False)
    if _RE_ARRAY_SUB.search(s):
        return ("%p", False)

    # Object types
    if s == 'instancetype':
        return ("%@", False)
    if s == 'id':
        return ("%@", False)
    # Blocks: Perl's /^*\(\^\).*$/ — the ^* is a quantified anchor (zero-width assertion
    # quantified to zero+), making it effectively a no-op. The pattern matches (^) ANYWHERE
    # in the string, not just at the start. So "void (^)(NSDictionary*, NSError*)" matches.
    if _RE_BLOCK.search(s):
        return ("%@", False)
    if _RE_WORD_PTR.match(s):
        return ("%@", False)
    if _RE_WORD_REF.match(s):
        return ("%@", False)

    # Floating-point types
    if s in _FLOAT_TYPES:
        return ("%f", False)

    # Special types
    if s == 'SEL':
        return ("%@", False)
    if s == 'Class':
        return ("%@", False)

    # Expanded struct types
    if s == 'NSRange':
        return ("(%d:%d)", False)
    if s in ('CGRect', 'NSRect'):
        return ("{{%g, %g}, {%g, %g}}", False)
    if s in ('CGPoint', 'NSPoint'):
        return ("{%g, %g}", False)
    if s in ('CGSize', 'NSSize'):
        return ("{%g, %g}", False)

    # Discarded types
    if _RE_CG_CF_VOID.match(s):
        return ("--", False)
    if s in _NS_HASH_MAP_TYPES:
        return ("--", False)
    if s.startswith('struct'):
        return ("--", False)

    # Fallthrough: treat as POD
    return ("0x%llx", True)


def print_arg_for_arg_type(argtype, argname):
    formatchar, fallthrough = format_char_for_arg_type(argtype)
    if formatchar == "--":
        return None

    s = argtype.strip()

    if s == 'SEL':
        return "NSStringFromSelector(" + argname + ")"
    if s == 'Class':
        return argname
    if s == 'NSRange':
        return argname + ".location, " + argname + ".length"
    if s in ('CGRect', 'NSRect'):
        return (argname + ".origin.x, " + argname + ".origin.y, " +
                argname + ".size.width, " + argname + ".size.height")
    if s in ('CGPoint', 'NSPoint'):
        return argname + ".x, " + argname + ".y"
    if s in ('CGSize', 'NSSize'):
        return argname + ".width, " + argname + ".height"
    if _RE_NS_LONG_TYPES.match(s):
        return "(long)" + argname
    if _RE_NS_UINTEGER.match(s):
        return "(unsigned long)" + argname

    return ("(uint64_t)" if fallthrough else "") + argname


def type_encoding_for_arg_type(argtype):
    s = argtype.strip()

    if s == 'char':
        return "c"
    if s == 'int':
        return "i"
    if s == 'short':
        return "s"
    if s == 'long':
        return "l"
    if s == 'long long':
        return "q"

    if _RE_UNSIGNED_CHAR.match(s):
        return "C"
    if _RE_UNSIGNED_INT.match(s):
        return "I"
    if _RE_UNSIGNED_SHORT.match(s):
        return "S"
    if _RE_UNSIGNED_LONG.match(s):
        return "L"
    if _RE_UNSIGNED_LONG_LONG.match(s):
        return "Q"

    if s == 'float':
        return "f"
    if s == 'double':
        return "d"
    if s in ('bool', '_Bool'):
        return "B"

    if s == 'void':
        return "v"

    if _RE_CHAR_PTR.match(s):
        return "*"

    if s == 'id':
        return "@"
    if s == 'instancetype':
        return "@"
    if s == 'Class':
        return "#"
    if s == 'SEL':
        return ":"

    m = _RE_BASE_PTR.match(s)
    if m:
        sub_encoding = type_encoding_for_arg_type(m.group(1))
        if sub_encoding is None:
            return None
        return "^" + sub_encoding

    return None


def declaration_for_type_with_name(argtype, argname):
    if not _RE_FUNC_PTR_DECL.search(argtype):
        return argtype + " " + argname

    substring = argtype
    result = matched_parenthesis_set(substring, atstart=False)
    if result is None:
        return argtype + " " + argname

    opening = result[0]
    closing = result[1]
    offset = 0

    while True:
        substring = substring[opening:closing - 1]
        offset += opening
        new_result = matched_parenthesis_set(substring, atstart=False)
        if new_result is None:
            break
        opening = new_result[0]
        closing = new_result[1]

    out = argtype
    insert_pos = offset - opening + closing - 1
    out = out[:insert_pos] + argname + out[insert_pos:]
    return out
