import re

# Pre-compiled regex patterns for performance
_RE_QUOTES = re.compile(r'(?<!\\)(["\'])(.*?)(?<!\\)\1')
_RE_SANITIZE = re.compile(r'[^a-zA-Z0-9_]')
_RE_PAREN_START = re.compile(r'^\s*\(')
_RE_PAREN_CHARS = re.compile(r'[;()]')


def _default_error_handler(msg):
    raise Exception(msg)


errorhandler = _default_error_handler


def quotes(line):
    result = []
    for m in _RE_QUOTES.finditer(line):
        result.append(m.start())
        result.append(m.end())
    return result


def falls_between(idx, pairs):
    i = 0
    while i < len(pairs):
        start = pairs[i]
        end = pairs[i + 1] if i + 1 < len(pairs) else None
        if start < idx and (end is None or end > idx):
            return True
        i += 2
    return False


def sanitize(input_str):
    return _RE_SANITIZE.sub('', input_str)


def matched_parenthesis_set(in_str, atstart=True, untilend=False):
    parens = []
    if not atstart or _RE_PAREN_START.match(in_str):
        parenmatch = in_str
        pdepth = 0
        pquotes = quotes(parenmatch)
        for m in _RE_PAREN_CHARS.finditer(parenmatch):
            if falls_between(m.start(), pquotes):
                continue
            char = m.group()
            if char == '(':
                if pdepth == 0:
                    parens.append(m.end())
                pdepth += 1
            elif char == ')':
                pdepth -= 1
                if pdepth == 0:
                    parens.append(m.end())
                    if not untilend:
                        break

    if len(parens) == 0:
        return None
    if len(parens) % 2 == 1:
        errorhandler("missing closing parenthesis")
    return parens


def nested_paren_string(in_str):
    result = matched_parenthesis_set(in_str)
    ret = [None, None]
    if result is not None:
        opening = result[0]
        closing = result[1]
        ret[0] = in_str[opening:closing - 1]
        in_str = in_str[closing:]
    ret[1] = in_str
    return ret


def smart_split(re_pattern, in_str, limit=0):
    if not in_str or in_str == "":
        return []

    q = quotes(in_str)
    parens_result = matched_parenthesis_set(in_str, atstart=False, untilend=True)
    parens = parens_result if parens_result is not None else []

    lstart = 0
    pieces = []

    if isinstance(re_pattern, str):
        compiled = re.compile(re_pattern)
    else:
        compiled = re_pattern

    for m in compiled.finditer(in_str):
        if (len(parens) > 0 and falls_between(m.start(), parens)) or falls_between(m.start(), q):
            continue
        piece = in_str[lstart:m.start()]
        pieces.append(piece)
        lstart = m.end()
        limit -= 1
        if limit == 1:
            break

    piece = in_str[lstart:]
    pieces.append(piece)
    return pieces
