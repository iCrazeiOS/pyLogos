class Patch:
    _logos_name = "Patch"

    line_directive_generator = None

    def __init__(self):
        self.line = -1
        self._range = []
        self.source = None
        self.squash = 0

    @property
    def range(self):
        return self._range

    @range.setter
    def range(self, value):
        self._range = list(value)

    @property
    def start(self):
        if len(self._range) > 0:
            return self._range[0]
        return None

    @start.setter
    def start(self, value):
        while len(self._range) < 1:
            self._range.append(None)
        self._range[0] = value

    @property
    def end(self):
        if len(self._range) > 1:
            return self._range[1]
        return None

    @end.setter
    def end(self, value):
        while len(self._range) < 2:
            self._range.append(None)
        self._range[1] = value

    def evalSource(self, source):
        lines = []
        if isinstance(source, list):
            for item in source:
                lines.extend(self.evalSource(item))
        elif source is not None and hasattr(source, 'eval'):
            lines.append(source.eval())
        elif source is not None:
            lines.append(source)
        else:
            # None source → empty string (Perl's undef joins as "")
            lines.append("")
        return lines

    def apply(self, lref):
        line = self.line
        start = self._range[0] if len(self._range) > 0 else None
        end = self._range[1] if len(self._range) > 1 else None
        source = self.source
        lines = self.evalSource(source)

        if start is None:
            if Patch.line_directive_generator is not None:
                lines.append(Patch.line_directive_generator(line))
            if self.squash:
                lref.append(''.join(lines))
            else:
                for i, l in enumerate(lines):
                    lref.insert(line + i, l)
        else:
            replacement = ''.join(lines)
            original = lref[line]
            lref[line] = original[:start] + replacement + original[end:]
