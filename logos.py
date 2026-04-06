#!/usr/bin/env python3
"""
Logos Preprocessor - Python port of logos.pl

Preprocesses Objective-C source files with special directives
(%hook, %orig, %init, etc.) for runtime hooking frameworks.
"""

import sys
import os
import re
import hashlib
import argparse

# Add lib to path
script_dir = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, script_dir)

from Logos import sigil
from Logos.util import quotes, falls_between, matched_parenthesis_set, smart_split
import Logos.util
from Logos.patch import Patch
from Logos.patch_source_generator import PatchSourceGenerator
from Logos.group import Group
from Logos.method import Method
from Logos.class_ import LogosClass
from Logos.subclass import Subclass
from Logos.static_class_group import StaticClassGroup
from Logos.property import Property
from Logos.function import Function
from Logos.Generator import Generator

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------

# --- Configuration ---
CONFIG = {
    'generator': 'MobileSubstrate',
    'warnings': 'default',
}
warnings_count = 0

# --- File state ---
filename = None
preprocessed = False
line_mapping = {}   # {physical_line: [filename, source_line]}
lines = []
patches = []

# --- Parser state ---
groups = []
current_group = None
current_class = None
current_method = None
new_method_type_encoding = None
current_function = None
classes = {}            # {class_name: reference_count}
nesting_stack = []
first_directive_position = []   # [lineno, pos] or empty
last_init_position = []         # [lineno, pos] or empty
depth_mapping = {"0:0": 0}     # {"line:pos": depth}
depth = 0
lineno = 0

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def file_warning(curline, reason):
    global warnings_count
    line_map = lookup_line_mapping(curline)
    fname = line_map[0]
    should_print = True
    if 'warnings' in CONFIG:
        if CONFIG['warnings'] == 'error':
            if warnings_count == 0:
                print("logos: warnings being treated as errors", file=sys.stderr)
        elif CONFIG['warnings'] == 'none':
            should_print = False
    if should_print:
        line_part = str(line_map[1]) + ":" if curline > -1 else ""
        print(f"{fname}:{line_part} warning: {reason}", file=sys.stderr)
    warnings_count += 1


def file_error(curline, reason):
    line_map = lookup_line_mapping(curline)
    fname = line_map[0]
    line_part = str(line_map[1]) + ":" if curline > -1 else ""
    print(f"{fname}:{line_part} error: {reason}", file=sys.stderr)
    sys.exit(1)


def nesting_error(curline, thisblock, reason):
    parts = reason.split(':')
    file_error(curline,
               f"{thisblock} inside a %{parts[0]}, opened at "
               f"{line_description_for_physical_line(int(parts[1]))}")


def nesting_must_contain(ln, trying, stackref, *search):
    result = nesting_contains(stackref, *search)
    if result is None:
        file_error(ln, f"{trying} found outside of {' or '.join(search)}")


def nesting_must_not_contain(ln, trying, stackref, *search):
    result = nesting_contains(stackref, *search)
    if result is not None:
        nesting_error(ln, trying, result)


def nesting_contains(stackref, *search):
    for nest in stackref:
        parts = nest.split(':')
        for find in search:
            if find == parts[0]:
                return nest
    return None


def nest_push(type_, line_, ref_stack):
    ref_stack.append(f"{type_}:{line_}")


def nest_pop(ref_stack):
    if not ref_stack:
        return None
    outgoing = ref_stack.pop()
    parts = outgoing.split(':')
    return parts[0]


def get_group(name):
    for g in groups:
        if g.name == name:
            return g
    return None


def lookup_line_mapping(fileline):
    fileline += 1
    for key in sorted(line_mapping.keys(), reverse=True):
        if fileline >= key:
            x = line_mapping[key]
            return (x[0], x[1] + (fileline - key))
    return None


def generate_line_directive_for_physical_line(physline):
    line_map = lookup_line_mapping(physline)
    fname = line_map[0]
    ln = line_map[1]
    if preprocessed:
        return f"# {ln} \"{fname}\""
    else:
        return f"#line {ln} \"{fname}\""


def line_description_for_physical_line(physline):
    line_map = lookup_line_mapping(physline)
    fname = line_map[0]
    ln = line_map[1]
    return f"{fname}:{ln}"


def _depth_key_sort(keys):
    """Sort depth-mapping keys descending by (line, pos)."""
    def sort_key(k):
        parts = k.split(':')
        return (-int(parts[0]), -int(parts[1]))
    return sorted(keys, key=sort_key)


def location_opening_depth_at_position_in_mapping(dref, fileline, pos, keys=None):
    if keys is None:
        keys = _depth_key_sort(dref.keys())
    for key in keys:
        dt = key.split(':')
        dt_line = int(dt[0])
        dt_pos = int(dt[1])
        if fileline > dt_line or (fileline == dt_line and pos >= dt_pos):
            return dt
    return None


def lookup_depth_mapping(fileline, pos, keys=None):
    dt = location_opening_depth_at_position_in_mapping(
        depth_mapping, fileline, pos, keys)
    if dt is None:
        return 0
    return depth_mapping[':'.join(dt)]


def patch_here(source, match_start, match_end):
    p = Patch()
    p.line = lineno
    p.range = (match_start, match_end)
    p.source = source
    patches.append(p)


def add_patch(p):
    patches.append(p)


def pretty_print_method(method):
    return f"{method.scope}[{method.class_.name} {method.selector}]"


def util_error_handler(msg):
    file_error(lineno, msg)


def default_constructor_source():
    result = []
    init_required_groups = [g for g in groups if g.initRequired]
    explicit_groups = [g for g in init_required_groups if g.explicit]
    if explicit_groups:
        file_error(lineno,
                   "Cannot generate an autoconstructor with multiple %groups. "
                   "Please explicitly create a constructor.")
    if init_required_groups:
        result.append(
            "static __attribute__((constructor)) void _logosLocalInit() {\n")
        for g in init_required_groups:
            if g.initialized:
                file_error(lineno,
                           f"re-%init of %group {g.name}, first initialized at "
                           f"{line_description_for_physical_line(g.initLine)}")
            result.append(PatchSourceGenerator(g, 'initializers'))
            result.append(" ")
            g.initLine = lineno
            g.initialized = True
        result.append("}\n")
    return result if result else None


# ---------------------------------------------------------------------------
# Pre-compiled regex patterns
# ---------------------------------------------------------------------------

# Phase 0 — file reading and comment stripping
RE_PREPROCESSED_FIRST = re.compile(r'^# (\d+) "(.*?)"$')
RE_PREPROCESSED_LINE = re.compile(r'^# (\d+) "(.*?)"')
RE_IF_BLOCK = re.compile(r'^#\s*if(?:n?def)?')
RE_ENDIF = re.compile(r'^#\s*endif')
RE_BLOCK_COMMENT_END = re.compile(r'^.*?\*/\s*')
RE_DOUBLE_SLASH = re.compile(r'//')
RE_INLINE_BLOCK_COMMENT = re.compile(r'/\*.*?\*/')
RE_BLOCK_COMMENT_START = re.compile(r'/\*.*$')
RE_IF_ZERO = re.compile(r'^\s*#\s*if\s+0')
RE_METHOD_DECL = re.compile(r'^\s*(%new.*?)?\s*([+-])\s*\(\s*(.*?)\s*\)')
RE_ORIG_CONTINUATION = re.compile(r'%orig[^;]*$')
RE_INIT_CONTINUATION = re.compile(r'%init[^;]*$')

# Phase 1 — depth tracking
RE_DEPTH_TOKENS = re.compile(
    r'(\{|\}|(?<=@)(interface|implementation|protocol|end))')
RE_PROTOCOL_FORWARD = re.compile(
    r'protocol(\s+([_\$A-Za-z0-9]+(,\s*)?)+;|\s*\()')

# Phase 1 — directive patterns
RE_HOOK = re.compile(r'%hook\s+([\$_\w\.]+)')
RE_SUBCLASS = re.compile(
    r'%subclass\s+([\$_\w]+)\s*:\s*([\$_\w]+)'
    r'\s*(<\s*(.*?)\s*>)?')
RE_GROUP = re.compile(r'%group\s+([\$_\w]+)')
RE_NON_DIGIT = re.compile(r'\D')
RE_CLASS = re.compile(r'%class\s+([+-])?([\$_\w]+)')
RE_C_PERCENT = re.compile(r'%c\(\s*([+-])?([\$_\w\.]+)\s*\)')
RE_NEW = re.compile(r'%new(\((.*?)\))?(?=\W?)')
RE_METHOD_SIG = re.compile(r'([+-])\s*\(\s*(.*?)\s*\)(?=\s*[\$\w:])')
RE_SELECTOR_PART = re.compile(
    r'\s*([\$\w]*)(\s*:\s*(\((.+?)\))?\s*([\$\w]+?)\b)?')
RE_VARIADIC = re.compile(r'\s*,\s*\.\.\.')
RE_ORIG = re.compile(r'%orig\b')
RE_AMP_ORIG = re.compile(r'&\s*%orig\b')
RE_LOG = re.compile(r'%log\b')
RE_CTOR = re.compile(r'%ctor\b')
RE_DTOR = re.compile(r'%dtor\b')
RE_INIT = re.compile(r'%init\b')
RE_COMMA_SPLIT = re.compile(r'\s*,\s*')
RE_EQUALS_SPLIT = re.compile(r'\s*=\s*')
RE_TRAILING_SEMIS = re.compile(r'(\s*;)*')
RE_END = re.compile(r'%end\b')
RE_CONFIG = re.compile(r'%config\s*\(\s*(\w+)\s*=\s*(.*?)\s*\)')
RE_PROPERTY = re.compile(
    r'%property\s*'
    r'(?:\(([^)]*)\))?\s*'
    r'(.*?)'
    r'\b([a-zA-Z_\$][\w\$]*)\s*;')
RE_PROP_ATTR_SPLIT = re.compile(r'\(?\s*,\s*\)?')
RE_GETTER_ATTR = re.compile(r'getter=(\w+)')
RE_SETTER_ATTR = re.compile(r'setter=(\w+):')
RE_HOOKF = re.compile(r'%hookf\b')

# Phase 2 — insertion point detection
RE_BLANK_LINE = re.compile(r'^\s*$')
RE_IMPORT_LINE = re.compile(r'^\s*([#@]import|#include)\s')

# Outer-loop regex: find potential directive starts.
# \B ensures the % (or & or +/-) is NOT preceded by a word character.
DIRECTIVE_LOOKAHEAD_RE = re.compile(
    r'\B(?=(%\w|&\s*%\w|[+-]\s*\(\s*.*?\s*\)))')

# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    global CONFIG, warnings_count, filename, preprocessed
    global line_mapping, lines, patches
    global groups, current_group, current_class, current_method
    global new_method_type_encoding, current_function
    global classes, nesting_stack, first_directive_position, last_init_position
    global depth_mapping, depth, lineno

    script = os.path.basename(__file__)

    # ---- argument parsing --------------------------------------------------
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('-c', '--config', action='append', default=[])
    parser.add_argument('-h', '--help', action='store_true', dest='show_help')
    parser.add_argument('filename', nargs='?')
    args = parser.parse_args()

    if args.show_help:
        print(f"Usage: {script} [options] <filename>\n"
              "Options:\n"
              "  [-c|--config]\t\tModify Logos' configuration "
              "(MobileSubstrate, default)\n"
              "     -c generator=[internal|libhooker|MobileSubstrate]\n"
              "     -c warnings=[default|error|none]\n"
              "  [-h|--help]\t\tDisplay this page")
        sys.exit(0)

    for cfg in args.config:
        if '=' in cfg:
            key, val = cfg.split('=', 1)
            CONFIG[key] = val

    filename = args.filename
    if not filename:
        print(f"Usage: {script} [options] <filename>\n"
              f"Run {script} --help for more details", file=sys.stderr)
        sys.exit(1)

    try:
        with open(filename, 'r') as f:
            file_lines = f.readlines()
    except IOError:
        print(f"Could not open {filename}.", file=sys.stderr)
        sys.exit(1)

    # Wire up callbacks
    Logos.util.errorhandler = util_error_handler
    Patch.line_directive_generator = generate_line_directive_for_physical_line

    # ---- check if already preprocessed ------------------------------------
    preprocessed = False
    if file_lines:
        firstline = file_lines[0].rstrip('\n')
        m = RE_PREPROCESSED_FIRST.match(firstline)
        if m:
            preprocessed = True
            filename = m.group(2)

    # ======================================================================
    # Phase 0 — read file, strip comments, glue multi-line declarations
    # ======================================================================
    lines = []
    readignore = False
    built = ""
    building = False
    iflevel = -1
    file_lineno = 0

    for raw_line in file_lines:
        line = raw_line.rstrip('\n')
        file_lineno += 1

        # -- preprocessor line-mapping directives ---------------------------
        if preprocessed:
            m_pp = RE_PREPROCESSED_LINE.match(line)
            if m_pp:
                line_mapping[file_lineno + 1] = [m_pp.group(2),
                                                  int(m_pp.group(1))]

        # -- readignore handling (#if 0 blocks / multi-line comments) -------
        if readignore:
            if iflevel > -1 and RE_IF_BLOCK.match(line):
                iflevel += 1
            elif iflevel > 0:
                m_endif = RE_ENDIF.match(line)
                if m_endif:
                    line = line[m_endif.end():]
                    iflevel -= 1

            if iflevel == 0:
                readignore = False
                iflevel = -1
                # line already set to postmatch of #endif above
            elif iflevel == -1:
                m_ce = RE_BLOCK_COMMENT_END.match(line)
                if m_ce:
                    readignore = False
                    line = line[m_ce.end():]

        if readignore:
            lines.append("")
            continue

        # -- comment removal (with redo-loop) -------------------------------
        while True:
            q = quotes(line)

            # Delete single-line // comments
            found_slashslash = False
            has_block_end = '*/' in line
            for m_sl in RE_DOUBLE_SLASH.finditer(line):
                if has_block_end or falls_between(m_sl.start(), q):
                    continue
                line = line[:m_sl.start()]
                found_slashslash = True
                break
            if found_slashslash:
                continue  # redo — recompute quotes, rescan

            # Delete single-line /* ... */ comments
            found_block = False
            for m_bl in RE_INLINE_BLOCK_COMMENT.finditer(line):
                if falls_between(m_bl.start(), q):
                    continue
                line = line[:m_bl.start()] + line[m_bl.end():]
                found_block = True
                break
            if found_block:
                continue  # redo

            break  # nothing removed — exit redo loop

        # -- start of multi-line /* comment ---------------------------------
        q = quotes(line)
        multiline_found = False
        for m_ml in RE_BLOCK_COMMENT_START.finditer(line):
            if falls_between(m_ml.start(), q):
                continue
            line = line[:m_ml.start()]
            lines.append(line)
            readignore = True
            multiline_found = True
            break
        if multiline_found:
            continue

        # -- #if 0 ----------------------------------------------------------
        if RE_IF_ZERO.match(line):
            iflevel = 1
            lines.append("")
            readignore = True
            continue

        # -- line building (glue multi-line declarations) -------------------
        if not readignore:
            if not building:
                should_build = False
                match_start = 0

                # Try method declaration pattern
                m_meth = RE_METHOD_DECL.search(line)
                if m_meth:
                    match_start = m_meth.start()
                    should_build = True

                if not should_build:
                    m_orig = RE_ORIG_CONTINUATION.search(line)
                    if m_orig:
                        match_start = m_orig.start()
                        should_build = True

                if not should_build:
                    m_init = RE_INIT_CONTINUATION.search(line)
                    if m_init:
                        match_start = m_init.start()
                        should_build = True

                if should_build:
                    brace_pos = line.find('{')
                    semi_pos = line.find(';')
                    # -1 (not found) < match_start is true for match_start >= 0
                    if brace_pos < match_start and semi_pos < match_start:
                        q2 = quotes(line)
                        if falls_between(match_start, q2):
                            lines.append(line)
                            continue
                        building = True
                        built = line
                        lines.append("")
                        continue
                    else:
                        should_build = False

                # Normal line (no building triggered)
                lines.append(line)
                continue

            else:  # building == True
                line = line.lstrip()
                built += " " + line
                if '{' in line or ';' in line:
                    lines.append(built)
                    building = False
                    built = ""
                    continue
                lines.append("")
                continue

    if building:
        lines.append(built)

    # Default line mapping for non-preprocessed files
    if not line_mapping:
        line_mapping[0] = [filename, 0]

    # ======================================================================
    # Phase 1 — directive processing
    # ======================================================================
    lineno = 0

    default_group = Group()
    default_group.name = "_ungrouped"
    default_group.explicit = 0
    static_class_group = StaticClassGroup()
    groups = [default_group]

    current_group = default_group
    current_class = None
    current_method = None
    new_method_type_encoding = None
    current_function = None
    classes = {}
    nesting_stack = []
    first_directive_position = []
    last_init_position = []
    depth_mapping = {"0:0": 0}
    depth = 0

    for line in lines:
        q = quotes(line)

        # -- brace / ObjC keyword depth mapping -----------------------------
        depths_for_current_line = {}
        depths_for_current_line[f"{lineno}:0"] = depth

        for m_brace in RE_DEPTH_TOKENS.finditer(line):
            if falls_between(m_brace.start(), q):
                continue

            depth_token = f"{lineno}:{m_brace.start() + 1}"
            matched = m_brace.group()

            if matched == '{':
                depth += 1
            elif matched == 'implementation':
                depth += 1
            elif matched == 'interface':
                depth += 1
            elif matched == 'protocol':
                remaining = line[m_brace.start():]
                if not RE_PROTOCOL_FORWARD.match(remaining):
                    depth += 1
            elif matched == '}':
                depth -= 1
            elif matched == 'end':
                depth -= 1

            if depth < 0:
                file_error(lineno,
                           f"fell off the face of the planet when we found "
                           f"a '{matched}'")

            depth_mapping[depth_token] = depth
            depths_for_current_line[depth_token] = depth

        # -- directive scanning ---------------------------------------------
        pos = 0
        while pos <= len(line):
            m_outer = DIRECTIVE_LOOKAHEAD_RE.search(line, pos)
            if m_outer is None:
                break

            found_pos = m_outer.start()

            if falls_between(found_pos, q):
                pos = found_pos + 1
                continue

            # Depth at this position
            dt = location_opening_depth_at_position_in_mapping(
                depths_for_current_line, lineno, found_pos)
            if dt is None:
                directive_depth = 0
            else:
                directive_depth = depths_for_current_line[':'.join(dt)]

            rest = line[found_pos:]
            matched_directive = False

            # ---- %hook <identifier> ----------------------------------------
            m_d = RE_HOOK.match(rest)
            if m_d:
                if directive_depth >= 1:
                    file_error(lineno,
                               "%hook does not make sense inside a block")
                nesting_must_not_contain(lineno, "%hook", nesting_stack,
                                         "hook", "subclass")

                if not first_directive_position:
                    first_directive_position[:] = [lineno, found_pos]

                nest_push("hook", lineno, nesting_stack)

                class_name = m_d.group(1)
                expr = None
                if '.' in class_name:
                    file_warning(
                        lineno,
                        f"Hooking Objective-C bridged Swift class "
                        f"{class_name} has unintuitive behaviour and won't "
                        f"catch all invocations, see "
                        f"https://theos.dev/docs/swift for more details.")
                    expr = f'objc_getClass("{class_name}")'
                    class_name = class_name.replace('.', '_')

                current_class = current_group.addClassNamed(class_name)
                if expr is not None:
                    current_class.expression = expr
                classes[current_class.name] = \
                    classes.get(current_class.name, 0) + 1

                patch_here(None, found_pos, found_pos + m_d.end())
                pos = found_pos + m_d.end()
                matched_directive = True

            # ---- %subclass <id> : <id> <protocols> -------------------------
            if not matched_directive:
                m_d = RE_SUBCLASS.match(rest)
                if m_d:
                    if directive_depth >= 1:
                        file_error(lineno,
                                   "%subclass does not make sense inside "
                                   "a block")
                    nesting_must_not_contain(lineno, "%subclass",
                                             nesting_stack,
                                             "hook", "subclass")

                    if not first_directive_position:
                        first_directive_position[:] = [lineno, found_pos]

                    nest_push("subclass", lineno, nesting_stack)

                    classname = m_d.group(1)
                    superclassname = m_d.group(2)
                    superclass = current_group.addClassNamed(superclassname)
                    superclass.required = 1
                    current_class = Subclass()
                    current_class.name = classname
                    current_class.superclass = superclass
                    if m_d.group(3) is not None and m_d.group(4) is not None:
                        protocols = RE_COMMA_SPLIT.split(m_d.group(4))
                        for proto in protocols:
                            current_class.addProtocol(proto)
                    current_group.addClass(current_class)

                    static_class_group.addDeclaredOnlyClass(classname)
                    classes[superclassname] = \
                        classes.get(superclassname, 0) + 1
                    classes[classname] = classes.get(classname, 0) + 1

                    patch_here(None, found_pos, found_pos + m_d.end())
                    pos = found_pos + m_d.end()
                    matched_directive = True

            # ---- %group <identifier> ---------------------------------------
            if not matched_directive:
                m_d = RE_GROUP.match(rest)
                if m_d:
                    if directive_depth >= 1:
                        file_error(lineno,
                                   "%group does not make sense inside a block")

                    # Check for hooks in nesting stack
                    for idx, ns_entry in enumerate(nesting_stack):
                        if 'hook' in ns_entry:
                            hookno_str = RE_NON_DIGIT.sub('', ns_entry)
                            hookno = int(hookno_str) if hookno_str else 0
                            if hookno < lineno:
                                file_error(lineno,
                                           "%group does not make sense "
                                           "inside a hook")

                    nesting_must_not_contain(lineno, "%group", nesting_stack,
                                             "group")

                    if not first_directive_position:
                        first_directive_position[:] = [lineno, found_pos]

                    nest_push("group", lineno, nesting_stack)

                    current_group = get_group(m_d.group(1))
                    patch_source = None
                    if current_group is None:
                        current_group = Group()
                        current_group.name = m_d.group(1)
                        groups.append(current_group)
                        captured_group = current_group
                        patch_source = PatchSourceGenerator(
                            captured_group, 'declarations')
                    patch_here(patch_source, found_pos,
                               found_pos + m_d.end())
                    pos = found_pos + m_d.end()
                    matched_directive = True

            # ---- %class [+-]<identifier>  (deprecated) ---------------------
            if not matched_directive:
                m_d = RE_CLASS.match(rest)
                if m_d:
                    if not first_directive_position:
                        first_directive_position[:] = [lineno, found_pos]

                    file_warning(
                        lineno,
                        "%class is deprecated and will be removed in the "
                        "future; consider switching to inline %c()")

                    scope = m_d.group(1) if m_d.group(1) else "-"
                    classname = m_d.group(2)
                    if scope == "+":
                        static_class_group.addUsedMetaClass(classname)
                    else:
                        static_class_group.addUsedClass(classname)
                    classes[classname] = classes.get(classname, 0) + 1
                    patch_here(None, found_pos, found_pos + m_d.end())
                    pos = found_pos + m_d.end()
                    matched_directive = True

            # ---- %c([+-]<identifier>) --------------------------------------
            if not matched_directive:
                m_d = RE_C_PERCENT.match(rest)
                if m_d:
                    if not first_directive_position:
                        first_directive_position[:] = [lineno, found_pos]

                    scope = m_d.group(1) if m_d.group(1) else "-"
                    class_name = m_d.group(2)
                    unescaped_class_name = m_d.group(2)
                    if '.' in class_name:
                        file_warning(
                            lineno,
                            f"Dynamic lookup of Objective-C bridged Swift "
                            f"class {class_name} has unintuitive behaviour "
                            f"and won't catch all invocations, see "
                            f"https://theos.dev/docs/swift for more details.")
                        class_name = class_name.replace('.', '_')
                    if scope == "+":
                        static_class_group.addUsedMetaClass(
                            class_name, unescaped_class_name)
                    else:
                        static_class_group.addUsedClass(
                            class_name, unescaped_class_name)
                    classes[class_name] = classes.get(class_name, 0) + 1
                    patch_here(
                        PatchSourceGenerator(class_name,
                                             'classReferenceWithScope',
                                             scope),
                        found_pos, found_pos + m_d.end())
                    pos = found_pos + m_d.end()
                    matched_directive = True

            # ---- %new[(type)] ----------------------------------------------
            if not matched_directive:
                m_d = RE_NEW.match(rest)
                if m_d:
                    nesting_must_contain(lineno, "%new", nesting_stack,
                                         "hook", "subclass")
                    xtype = ""
                    if m_d.group(2):
                        xtype = m_d.group(2)
                    new_method_type_encoding = xtype
                    patch_here(None, found_pos, found_pos + m_d.end())
                    pos = found_pos + m_d.end()
                    matched_directive = True

            # ---- [+-] (<return>)<selector:args> ----------------------------
            if not matched_directive and current_class is not None:
                m_d = RE_METHOD_SIG.match(rest)
                if m_d and directive_depth < 1:
                    # Gasp! We've been moved to a different group!
                    if current_class.group != current_group:
                        classname = current_class.name
                        current_class = current_group.addClassNamed(classname)

                    scope = m_d.group(1)
                    return_type = m_d.group(2)

                    method = Method()
                    method.class_ = current_class
                    if scope == "+":
                        current_class.hasmetahooks = 1
                    else:
                        current_class.hasinstancehooks = 1

                    method.scope = scope
                    method.return_ = return_type

                    if new_method_type_encoding is not None:
                        method.setNew(1)
                        method.type = new_method_type_encoding
                        new_method_type_encoding = None

                    selparts = []
                    inner_pos = m_d.end()  # position within `rest`

                    # Parse selector parts: word, optional ": (argtype) argname"
                    while True:
                        m_sel = RE_SELECTOR_PART.match(rest, inner_pos)
                        if m_sel is None:
                            break
                        if not m_sel.group(1) and not m_sel.group(2):
                            # Both keyword and args empty — false positive
                            break

                        keyword = m_sel.group(1) if m_sel.group(1) else ""
                        selparts.append(keyword)

                        if not m_sel.group(2):
                            # No args — single keyword selector
                            inner_pos = m_sel.end()
                            break

                        arg_type = m_sel.group(4) if m_sel.group(3) else "id"
                        arg_name = m_sel.group(5)
                        method.addArgument(arg_type, arg_name)
                        inner_pos = m_sel.end()

                    # Check for variadic ", ..."
                    m_var = RE_VARIADIC.match(rest[inner_pos:])
                    if m_var:
                        method.variadic = 1
                        inner_pos += m_var.end()

                    method.selectorParts = selparts
                    current_class.addMethod(method)
                    current_method = method

                    patch_start = found_pos
                    patch_end = found_pos + inner_pos
                    p = Patch()
                    p.line = lineno
                    p.range = (patch_start, patch_end)
                    p.source = PatchSourceGenerator(method, 'definition')
                    add_patch(p)
                    pos = patch_end
                    matched_directive = True

            # ---- %orig (with optional parens) ------------------------------
            if not matched_directive:
                m_d = RE_ORIG.match(rest)
                if m_d:
                    if current_class is None:
                        if current_function is None:
                            file_error(lineno,
                                       "%orig does not make sense outside "
                                       "a function")
                        patch_start = found_pos
                        cur_pos = found_pos + m_d.end()

                        remaining = line[cur_pos:]
                        orig_args = None

                        paren_result = matched_parenthesis_set(remaining)
                        if paren_result is not None:
                            popen = paren_result[0]
                            pclose = paren_result[1]
                            orig_args = remaining[popen:pclose - 1]
                            cur_pos = cur_pos + pclose

                        p = Patch()
                        p.line = lineno
                        p.range = (patch_start, cur_pos)
                        if orig_args is None or len(orig_args) < 1:
                            if "..." in current_function.args:
                                file_error(
                                    lineno,
                                    "%orig requires arguments when hooking "
                                    "variadic functions")
                        p.source = PatchSourceGenerator(
                            current_function, 'originalFunctionCall',
                            orig_args)
                        add_patch(p)
                        pos = cur_pos
                    else:
                        nesting_must_contain(lineno, "%orig", nesting_stack,
                                             "hook", "subclass")
                        if current_method is None:
                            file_error(lineno,
                                       "%orig does not make sense outside "
                                       "a method")
                        if directive_depth < 1:
                            file_error(lineno,
                                       "%orig does not make sense outside "
                                       "a block")
                        if current_method.isNew:
                            file_warning(
                                lineno,
                                "%orig in new method "
                                f"{pretty_print_method(current_method)} "
                                "will be non-operative.")

                        patch_start = found_pos
                        cur_pos = found_pos + m_d.end()

                        remaining = line[cur_pos:]
                        orig_args = None

                        paren_result = matched_parenthesis_set(remaining)
                        if paren_result is not None:
                            popen = paren_result[0]
                            pclose = paren_result[1]
                            orig_args = remaining[popen:pclose - 1]
                            cur_pos = cur_pos + pclose

                        captured_method = current_method
                        p = Patch()
                        p.line = lineno
                        p.range = (patch_start, cur_pos)
                        p.source = PatchSourceGenerator(
                            captured_method, 'originalCall', orig_args)
                        add_patch(p)
                        pos = cur_pos

                    matched_directive = True

            # ---- &%orig (reference to original function pointer) -----------
            if not matched_directive:
                m_d = RE_AMP_ORIG.match(rest)
                if m_d:
                    if current_class is None:
                        if current_function is None:
                            file_error(lineno,
                                       "%orig does not make sense outside "
                                       "a function")
                        patch_start = found_pos
                        patch_end = patch_start + m_d.end()
                        p = Patch()
                        p.line = lineno
                        p.range = (patch_start, patch_end)
                        p.source = PatchSourceGenerator(
                            current_function, 'originalFunctionName')
                        add_patch(p)
                        pos = patch_end
                    else:
                        nesting_must_contain(lineno, "%orig", nesting_stack,
                                             "hook", "subclass")
                        if current_method is None:
                            file_error(lineno,
                                       "%orig does not make sense outside "
                                       "a method")
                        if directive_depth < 1:
                            file_error(lineno,
                                       "%orig does not make sense outside "
                                       "a block")
                        if current_method.isNew:
                            file_error(
                                lineno,
                                "no original method pointer for &%orig in "
                                "new method "
                                f"{pretty_print_method(current_method)}.")

                        captured_method = current_method
                        patch_here(
                            PatchSourceGenerator(captured_method,
                                                 'originalFunctionName'),
                            found_pos, found_pos + m_d.end())
                        pos = found_pos + m_d.end()

                    matched_directive = True

            # ---- %log ------------------------------------------------------
            if not matched_directive:
                m_d = RE_LOG.match(rest)
                if m_d:
                    nesting_must_contain(lineno, "%log", nesting_stack,
                                         "hook", "subclass")

                    patch_start = found_pos
                    cur_pos = found_pos + m_d.end()

                    remaining = line[cur_pos:]
                    log_args = None

                    paren_result = matched_parenthesis_set(remaining)
                    if paren_result is not None:
                        popen = paren_result[0]
                        pclose = paren_result[1]
                        log_args = remaining[popen:pclose - 1]
                        cur_pos = cur_pos + pclose

                    captured_method = current_method
                    p = Patch()
                    p.line = lineno
                    p.range = (patch_start, cur_pos)
                    p.source = PatchSourceGenerator(
                        captured_method, 'buildLogCall', log_args)
                    add_patch(p)
                    pos = cur_pos
                    matched_directive = True

            # ---- %ctor -----------------------------------------------------
            if not matched_directive:
                m_d = RE_CTOR.match(rest)
                if m_d:
                    if directive_depth >= 1:
                        file_error(lineno,
                                   "%ctor does not make sense inside a block")
                    nesting_must_not_contain(lineno, "%ctor", nesting_stack,
                                             "hook", "subclass")
                    prematch = line[:found_pos]
                    postmatch = line[found_pos + m_d.end():]
                    hash_input = prematch + str(lineno) + postmatch
                    md5_hash = hashlib.md5(
                        hash_input.encode()).hexdigest()[:8]
                    replacement = (
                        "static __attribute__((constructor)) void "
                        f"_logosLocalCtor_{md5_hash}"
                        "(int __unused argc, char __unused **argv, "
                        "char __unused **envp)")
                    patch_here(replacement, found_pos,
                               found_pos + m_d.end())
                    pos = found_pos + m_d.end()
                    matched_directive = True

            # ---- %dtor -----------------------------------------------------
            if not matched_directive:
                m_d = RE_DTOR.match(rest)
                if m_d:
                    if directive_depth >= 1:
                        file_error(lineno,
                                   "%dtor does not make sense inside a block")
                    nesting_must_not_contain(lineno, "%dtor", nesting_stack,
                                             "hook", "subclass")
                    prematch = line[:found_pos]
                    postmatch = line[found_pos + m_d.end():]
                    hash_input = prematch + str(lineno) + postmatch
                    md5_hash = hashlib.md5(
                        hash_input.encode()).hexdigest()[:8]
                    replacement = (
                        "static __attribute__((destructor)) void "
                        f"_logosLocalDtor_{md5_hash}"
                        "(int __unused argc, char __unused **argv, "
                        "char __unused **envp)")
                    patch_here(replacement, found_pos,
                               found_pos + m_d.end())
                    pos = found_pos + m_d.end()
                    matched_directive = True

            # ---- %init (with optional parens) ------------------------------
            if not matched_directive:
                m_d = RE_INIT.match(rest)
                if m_d:
                    if directive_depth < 1:
                        file_error(lineno,
                                   "%init does not make sense outside "
                                   "a block")
                    groupname = "_ungrouped"
                    patch_start = found_pos
                    cur_pos = found_pos + m_d.end()

                    remaining = line[cur_pos:]
                    argstring = None
                    paren_result = matched_parenthesis_set(remaining)
                    if paren_result is not None:
                        popen = paren_result[0]
                        pclose = paren_result[1]
                        argstring = remaining[popen:pclose - 1]
                        cur_pos = cur_pos + pclose

                    init_args = []
                    if argstring is not None:
                        init_args = smart_split(RE_COMMA_SPLIT, argstring)

                    tempgroupname = None
                    if init_args and init_args[0] and '=' not in init_args[0]:
                        tempgroupname = init_args[0]
                    if tempgroupname is not None:
                        groupname = tempgroupname
                        init_args.pop(0)

                    group = get_group(groupname)

                    if group is None:
                        file_error(lineno,
                                   f"%init for an undefined %group "
                                   f"{groupname}")
                    if group.initialized:
                        file_error(
                            lineno,
                            f"re-%init of %group {group.name}, first "
                            f"initialized at "
                            f"{line_description_for_physical_line(group.initLine)}")

                    for arg in init_args:
                        if '=' not in arg:
                            file_warning(lineno,
                                         f"unknown argument to %init: {arg}")
                            continue

                        parts = smart_split(RE_EQUALS_SPLIT, arg, 2)
                        if parts is None or len(parts) < 2 or \
                                parts[0] is None or parts[1] is None:
                            file_warning(lineno,
                                         "invalid symbol=expr in %init")
                            continue

                        expr = parts[1]
                        classname = parts[0].lstrip()
                        scope = "-"
                        if classname and classname[0] in ('+', '-'):
                            scope = classname[0]
                            classname = classname[1:]

                        cls = group.getClassNamed(classname)
                        if cls is not None:
                            if scope == "-":
                                cls.expression = expr
                            if scope == "+":
                                cls.metaexpression = expr
                            continue

                        functionname = parts[0]
                        func = group.getFunctionNamed(functionname)
                        if func is not None:
                            func.expression = expr
                            continue

                        file_warning(
                            lineno,
                            f"tried to set expression for unknown class or "
                            f"function {classname} in group {groupname}")

                    group.initLine = lineno
                    group.initialized = True

                    # Consume trailing semicolons
                    m_semi = RE_TRAILING_SEMIS.match(line[cur_pos:])
                    if m_semi:
                        cur_pos += m_semi.end()

                    p = Patch()
                    p.line = lineno
                    p.range = (patch_start, cur_pos)
                    p.source = PatchSourceGenerator(group, 'initializers')
                    add_patch(p)

                    last_init_position[:] = [lineno, cur_pos]
                    pos = cur_pos
                    matched_directive = True

            # ---- %end ------------------------------------------------------
            if not matched_directive:
                m_d = RE_END.match(rest)
                if m_d:
                    if directive_depth >= 1:
                        file_error(lineno,
                                   "%end does not make sense inside a block")
                    closing = nest_pop(nesting_stack)
                    if not closing:
                        file_error(lineno, "dangling %end")
                    if closing == "group":
                        current_group = get_group("_ungrouped")
                    if closing == "hook" or closing == "subclass":
                        current_class = None
                    patch_here(None, found_pos, found_pos + m_d.end())
                    pos = found_pos + m_d.end()
                    matched_directive = True

            # ---- %config(key=value) ----------------------------------------
            if not matched_directive:
                m_d = RE_CONFIG.match(rest)
                if m_d:
                    CONFIG[m_d.group(1)] = m_d.group(2)
                    patch_here(None, found_pos, found_pos + m_d.end())
                    pos = found_pos + m_d.end()
                    matched_directive = True

            # ---- %property -------------------------------------------------
            if not matched_directive:
                m_d = RE_PROPERTY.match(rest)
                if m_d:
                    nesting_must_contain(lineno, "%property", nesting_stack,
                                         "hook", "subclass")

                    current_class.hasinstancehooks = 1

                    if m_d.group(1) is None or m_d.group(1) == '':
                        file_error(
                            lineno,
                            "%property declaration is missing attributes "
                            "(e.g., nonatomic, retain, etc)")

                    attributes = RE_PROP_ATTR_SPLIT.split(m_d.group(1))
                    prop_type = m_d.group(2).strip()
                    prop_name = m_d.group(3)

                    assign = False
                    retain = False
                    copy = False
                    nonatomic = False
                    readonly = False
                    getter = None
                    setter = None

                    for attr in attributes:
                        attr = attr.strip()
                        if not attr:
                            continue
                        m_getter = RE_GETTER_ATTR.match(attr)
                        m_setter = RE_SETTER_ATTR.match(attr)
                        if m_getter:
                            getter = m_getter.group(1)
                        elif m_setter:
                            setter = m_setter.group(1)
                        elif attr in ('assign', 'unsafe_unretained'):
                            assign = True
                        elif attr in ('retain', 'strong'):
                            retain = True
                        elif attr == 'copy':
                            copy = True
                        elif attr == 'nonatomic':
                            nonatomic = True
                        elif attr == 'readonly':
                            readonly = True
                        elif attr in ('readwrite', 'weak', 'class'):
                            file_error(
                                lineno,
                                f"property attribute '{attr}' not supported.")
                        else:
                            file_error(
                                lineno,
                                f"unknown property attribute '{attr}'.")

                    if assign and retain:
                        file_error(
                            lineno,
                            "property attributes 'assign' and 'retain' are "
                            "mutually exclusive.")
                    if assign and copy:
                        file_error(
                            lineno,
                            "property attributes 'assign' and 'copy' are "
                            "mutually exclusive.")
                    if copy and retain:
                        file_error(
                            lineno,
                            "property attributes 'copy' and 'retain' are "
                            "mutually exclusive.")
                    if readonly:
                        if retain or copy or assign:
                            file_error(
                                lineno,
                                "property attribute 'readonly' cannot be "
                                "used with memory management attributes "
                                "(assign, retain, copy).")

                    prop = Property()
                    prop.class_ = current_class
                    prop.type = prop_type
                    prop.name = prop_name
                    prop.readonly = readonly

                    if not assign and not retain and not copy:
                        assign = True

                    policy = "OBJC_ASSOCIATION_"
                    if retain:
                        policy += "RETAIN"
                    elif copy:
                        policy += "COPY"
                    elif assign:
                        policy += "ASSIGN"
                    else:
                        file_error(
                            lineno,
                            "error: no 'assign', 'retain', or 'copy' "
                            "attribu...wait, how did you manage to get "
                            "here?\n")

                    if nonatomic:
                        if not assign:
                            policy += "_NONATOMIC"

                    prop.associationPolicy = policy
                    prop.retainFlag = retain
                    prop.copyFlag = copy
                    prop.nonatomicFlag = nonatomic

                    if current_group:
                        prop.group = current_group
                    else:
                        prop.group = default_group

                    if not getter:
                        getter = prop_name
                    prop.getter = getter

                    if not setter:
                        s = prop_name.replace(':', '')
                        s = s[0].upper() + s[1:] if s else s
                        setter = "set" + s
                    prop.setter = setter

                    current_class.addProperty(prop)

                    p = Patch()
                    p.line = lineno
                    p.range = (found_pos, found_pos + m_d.end())
                    p.source = PatchSourceGenerator(prop, 'definition')
                    add_patch(p)
                    pos = found_pos + m_d.end()
                    matched_directive = True

            # ---- %hookf ----------------------------------------------------
            if not matched_directive:
                m_d = RE_HOOKF.match(rest)
                if m_d:
                    if directive_depth >= 1:
                        file_error(lineno,
                                   "%hookf does not make sense inside "
                                   "a block")
                    nesting_must_not_contain(lineno, "%hookf", nesting_stack,
                                             "hook", "subclass")

                    if not first_directive_position:
                        first_directive_position[:] = [lineno, found_pos]

                    patch_start = found_pos
                    cur_pos = found_pos + m_d.end()

                    remaining = line[cur_pos:]
                    argument_string = None
                    func_args = []

                    paren_result = matched_parenthesis_set(remaining)
                    if paren_result is not None:
                        popen = paren_result[0]
                        pclose = paren_result[1]
                        argument_string = remaining[popen:pclose - 1]
                        cur_pos = cur_pos + pclose
                        func_args = smart_split(
                            RE_COMMA_SPLIT, argument_string)

                    current_function = current_group.addFunction(func_args)

                    p = Patch()
                    p.line = lineno
                    p.range = (patch_start, cur_pos)
                    p.source = PatchSourceGenerator(
                        current_function, 'declaration')
                    add_patch(p)
                    pos = cur_pos
                    matched_directive = True

            # ---- no directive matched — advance past this position ---------
            if not matched_directive:
                pos = found_pos + 1
                continue

        lineno += 1

    # ======================================================================
    # Phase 2 — post-processing, patch application, output
    # ======================================================================

    # Check for unclosed nesting
    while nesting_stack:
        closing = nesting_stack.pop()
        parts = closing.split(':')
        file_warning(
            lineno,
            f"missing %end (%{parts[0]} opened at "
            f"{line_description_for_physical_line(int(parts[1]))} "
            f"extends to EOF)")

    # Activate the chosen generator
    Generator.use(CONFIG['generator'])

    # Check for generator preamble
    has_generator_preamble = preprocessed
    if not has_generator_preamble:
        has_generator_preamble = Generator.for_(None).findPreamble(lines)

    if first_directive_position:
        # Find insertion point: walk backwards from first directive to find
        # a blank line at depth 0 (or an import/include line).
        depth_keys = _depth_key_sort(depth_mapping.keys())
        ins_line = first_directive_position[0]
        ins_pos = first_directive_position[1]
        while True:
            d = lookup_depth_mapping(ins_line, ins_pos, depth_keys)
            above = None
            if ins_line == 0:
                above = ""
            if preprocessed and above is None:
                lm = lookup_line_mapping(ins_line)
                if lm[0] == filename and lm[1] == 1:
                    above = ""
            if above is None:
                above = lines[ins_line - 1]

            if d == 0 and (RE_BLANK_LINE.match(above) or
                           RE_IMPORT_LINE.match(above)):
                break

            if ins_pos == 0:
                ins_line -= 1
            ins_pos = 0

        # Build preamble patch
        p = Patch()
        p.line = ins_line
        patchsource = []
        if not has_generator_preamble:
            patchsource.append(PatchSourceGenerator(None, 'preamble'))
        patchsource.append(PatchSourceGenerator(None, 'staticDeclarations'))
        patchsource.append(
            PatchSourceGenerator(None, 'generateClassList',
                                 *list(classes.keys())))
        patchsource.append(
            PatchSourceGenerator(groups[0], 'declarations'))
        patchsource.append(
            PatchSourceGenerator(static_class_group, 'declarations'))
        p.source = patchsource
        add_patch(p)

        # If no %init seen, generate default constructor
        if not last_init_position:
            p = Patch()
            p.line = len(lines)
            p.squash = 1
            p.source = default_constructor_source()
            add_patch(p)

    # Check for uninitialized groups
    uninit_groups = [g.name for g in groups
                     if not g.initialized and g.initRequired]
    if uninit_groups:
        plural = "" if len(uninit_groups) == 1 else "s"
        file_error(lineno,
                   f"non-initialized hook group{plural}: "
                   f"{', '.join(uninit_groups)}")

    # Sort patches: descending by line, then descending by start position
    sorted_patches = sorted(
        patches,
        key=lambda p: (
            p.line,
            p.start if p.start is not None else -1),
        reverse=True)

    # Dump support (%config dump=yaml)
    if 'dump' in CONFIG:
        if CONFIG['dump'] == 'yaml':
            try:
                import yaml
                dump_data = {
                    'linemap': line_mapping,
                    'depthmap': depth_mapping,
                    'groups': groups,
                    'patches': patches,
                    'lines': lines,
                    'config': CONFIG,
                }
                print(yaml.dump(dump_data), file=sys.stderr)
            except ImportError:
                pass

    # Exit on warnings-as-errors
    if warnings_count > 0 and CONFIG.get('warnings') == 'error':
        sys.exit(1)

    # Apply patches in reverse order
    for p in sorted_patches:
        p.apply(lines)

    # Prepend line directive for non-preprocessed files
    if not preprocessed:
        lines.insert(0, generate_line_directive_for_physical_line(0))

    # Output
    for oline in lines:
        if oline is not None:
            print(oline)


if __name__ == '__main__':
    main()
