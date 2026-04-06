from ... import sigil


class BaseStaticClassGroupGenerator:
    @classmethod
    def _methodForClassWithScope(cls, classname, scope, group):
        methodname = sigil("static_metaclass_lookup" if scope == "+" else "static_class_lookup", classname)
        lookup_method = "objc_getMetaClass" if scope == "+" else "objc_getClass"

        classname = group.unescapedClassNameForClass(classname)
        # This is a dirty assumption - we believe that we will always be using a compiler that defines __GNUC__ and respects GNU C attributes.
        return ("static __inline__ __attribute__((always_inline)) __attribute__((unused)) Class "
                + methodname + "(void) { static Class _klass; if(!_klass) { _klass = "
                + lookup_method + "(\"" + classname + "\"); } return _klass; }")

    @classmethod
    def declarations(cls, group):
        result = ""
        if len(group.usedMetaClasses) + len(group.usedClasses) + len(group.declaredOnlyClasses) == 0:
            return ""
        for classname in group.usedMetaClasses:
            result += cls._methodForClassWithScope(classname, "+", group)
        for classname in group.usedClasses:
            result += cls._methodForClassWithScope(classname, "-", group)
        return result

    @classmethod
    def initializers(cls, group):
        return ""

