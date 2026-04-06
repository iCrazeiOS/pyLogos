#!/usr/bin/env python3
# logify.py
############
# Converts an Objective-C header file (or anything containing an @interface and method definitions)
# into a Logos input file which causes all function calls to be logged.
#
# Accepts input on stdin or via filename specified on the commandline.
#
# Lines are only processed if we're in an @interface, so you can run this on a file containing
# an @implementation, as well.
############

import sys
import os
import re
import argparse
import fileinput

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

from Logos.method import format_char_for_arg_type, print_arg_for_arg_type
from Logos.util import smart_split
import Logos.util

# Pre-compiled regex patterns for performance
_RE_WHITESPACE = re.compile(r'\s')
_RE_METHOD_DECL = re.compile(r'^[+-]\s*\((.*?)\).*?(?=;)')
_RE_RETURN_TYPE = re.compile(r'^[+-]\s*\((.*?)\)')
_RE_PROPERTY = re.compile(r'^\s*@property\s*\((.*?)\)\s*(.*?)\b([$a-zA-Z_][$_a-zA-Z0-9]*)(?=;)')
_RE_READONLY = re.compile(r'readonly')
_RE_INTERFACE_START = re.compile(r'^@interface\s+(.*?)\s*[:(]')
_RE_INTERFACE_END = re.compile(r'^@end')
_RE_PAREN_CONTENT = re.compile(r'\([^()]*\)')


def main():
    script = os.path.basename(__file__)

    if len(sys.argv) == 1 and sys.stdin.isatty():
        sys.exit("Usage: %s <filename>\nRun %s --help for more details" % (script, script))

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('-i', '--include', default=None)
    parser.add_argument('-e', '--exclude', default=None)
    parser.add_argument('-h', '--help', action='store_true', dest='show_help')
    parser.add_argument('files', nargs='*')

    args = parser.parse_args()

    if args.show_help:
        print("Usage: %s [options] filename ...\n"
              "Options:\n"
              "  [-i|--include]\tComma-separated list of methods to include\n"
              "\t -i \"launchedTaskWithLaunchPath:arguments:,arguments\" (for example)\n"
              "  [-e|--exclude]\tComma-separated list of methods to exclude\n"
              "\t -e \"launchedTaskWithLaunchPath:arguments:,arguments\" (for example)\n"
              "  [-h|--help]\t\tDisplay this page" % script)
        sys.exit(0)

    if args.include is not None and args.exclude is not None:
        sys.exit("Error: --include and --exclude are mutually exclusive\nRun %s --help for more details" % script)

    fi = fileinput.input(files=args.files if args.files else ('-',))

    Logos.util.errorhandler = lambda msg: sys.exit(
        "%s:%d: error: %s" % (fi.filename(), fi.lineno(), msg)
    )

    interface = 0
    logged_methods = []

    def is_logged(s):
        s_stripped = _RE_WHITESPACE.sub('', s)
        if not logged_methods or s_stripped not in logged_methods:
            logged_methods.append(s_stripped)
            return False
        return True

    def log_line_for_declaration(declaration):
        m = _RE_RETURN_TYPE.match(declaration)

        if (args.include is not None or args.exclude is not None) and not should_log_declaration(declaration):
            return ""

        rtype = m.group(1)
        innards = "%log; "
        if rtype != "void":
            if rtype == "instancetype":
                rtype = "id"
            innards += "%s r = %%orig; " % rtype
            print_arg = print_arg_for_arg_type(rtype, "r")
            if print_arg is not None:
                format_char = format_char_for_arg_type(rtype)[0]
                innards += 'NSLog(@" = %s", %s); ' % (format_char, print_arg)
            innards += "return r; "
        else:
            innards += "%orig; "

        return "%s { %s}\n" % (declaration, innards)

    def should_log_declaration(s):
        # Remove anything within parentheses (inclusive) — strips type info
        s = _RE_PAREN_CONTENT.sub('', s)
        # Remove instance/class method prefix and non-alphanumeric (keep : and whitespace)
        s = re.sub(r'[^a-zA-Z0-9:\s]', '', s)

        opt = args.include
        if args.exclude is not None:
            opt = args.exclude

        filters = [opt]
        # If multiple methods passed
        if ',' in opt:
            filters = opt.split(',')

        # If the desired method(s) and current method have params
        if any(':' in f for f in filters) and ':' in s:
            # Append space after colons
            s = s.replace(':', ': ')
            arr = s.split()
            # Remove bits without a colon (e.g., parameter names)
            arr = [x for x in arr if ':' in x]
            s = ''.join(arr)

        # Strip any remaining whitespace
        s = _RE_WHITESPACE.sub('', s)

        # Check to see if we've got a match
        for f in filters:
            if args.exclude is not None and f == s:
                # Don't logify
                return False
            elif f == s:
                # Do logify
                return True

        # Cases when no filter matched
        if args.exclude is not None:
            return True
        else:
            return False

    for line in fi:
        # Regular methods
        m = _RE_METHOD_DECL.match(line)
        if m and interface == 1:
            full_match = m.group(0)
            if not is_logged(full_match):
                sys.stdout.write(log_line_for_declaration(full_match))
            continue

        # Properties (setter/getter)
        m = _RE_PROPERTY.match(line)
        if m and interface == 1:
            attributes = smart_split(r'\s*,\s*', m.group(1))
            property_name = m.group(3)
            type_ = m.group(2).rstrip()
            readonly = sum(1 for a in attributes if _RE_READONLY.search(a))
            methods = {
                "setter": "set" + property_name[0].upper() + property_name[1:] + ":",
                "getter": property_name
            }
            for attribute in attributes:
                if '=' not in attribute:
                    continue
                x = smart_split(r'\s*=\s*', attribute)
                methods[x[0]] = x[1]

            if readonly == 0:
                setter = "- (void)%s(%s)%s" % (methods["setter"], type_, property_name)
                if not is_logged(setter):
                    sys.stdout.write(log_line_for_declaration(setter))

            getter = "- (%s)%s" % (type_, methods["getter"])
            if not is_logged(getter):
                sys.stdout.write(log_line_for_declaration(getter))
            continue

        # Interface start
        m = _RE_INTERFACE_START.match(line)
        if m and interface == 0:
            sys.stdout.write("%%hook %s\n" % m.group(1))
            interface = 1
            continue

        # Interface end
        if _RE_INTERFACE_END.match(line) and interface == 1:
            sys.stdout.write("%end\n")
            interface = 0

    fi.close()


if __name__ == '__main__':
    main()
