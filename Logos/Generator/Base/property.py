import re

from ... import sigil


class BasePropertyGenerator:
    @classmethod
    def getterName(cls, property_obj):
        return sigil("property", property_obj.group.name, property_obj.class_.name, property_obj.getter)

    @classmethod
    def setterName(cls, property_obj):
        return sigil("property", property_obj.group.name, property_obj.class_.name, property_obj.setter)

    # addAttribute(attributeList, attributeCount, attributeName, attributeValue)
    #
    # attributeName is one of the property attribute characters, it will be "stringified" for you
    # attribute value must be a variable or something else; it will NOT be "stringified" for you; omit it to use ""
    @classmethod
    def addAttribute(cls, attr_list, counter, name, value='""'):
        return " " + attr_list + "[" + counter + "++] = (objc_property_attribute_t) { \"" + name + "\", " + value + " };"

    @classmethod
    def definition(cls, property_obj):
        readonly = property_obj.readonly
        property_type = property_obj.type
        property_class = property_obj.class_.name
        property_getter = property_obj.getter
        property_getter_name = cls.getterName(property_obj)
        property_setter = property_obj.setter
        property_setter_name = cls.setterName(property_obj)
        property_association_policy = property_obj.associationPolicy
        wrap_value = "RETAIN" not in property_association_policy and "COPY" not in property_association_policy

        if not readonly:
            # Build getter
            getter_func = "__attribute__((used)) "  # If the property is never accessed, clang's optimizer will remove the getter/setter if this attribute isn't specified
            getter_func += "static " + property_type + " " + property_getter_name + "(" + property_class + " * __unused self, SEL __unused _cmd) "
            if wrap_value:
                getter_func += "{ NSValue * value = objc_getAssociatedObject(self, (void *)" + property_getter_name + "); " + property_type + " rawValue; [value getValue:&rawValue]; return rawValue; }"
            else:
                getter_func += "{ return (" + property_type + ")objc_getAssociatedObject(self, (void *)" + property_getter_name + "); }"

            # Build setter
            setter_func = "__attribute__((used)) "  # If the property is never accessed, clang's optimizer will remove the getter/setter if this attribute isn't specified
            setter_func += "static void " + property_setter_name + "(" + property_class + " * __unused self, SEL __unused _cmd, " + property_type + " rawValue) "
            if wrap_value:
                setter_func += "{ NSValue * value = [NSValue valueWithBytes:&rawValue objCType:@encode(" + property_type + ")]; objc_setAssociatedObject(self, (void *)" + property_getter_name + ", value, OBJC_ASSOCIATION_RETAIN_NONATOMIC); }"
            else:
                setter_func += "{ objc_setAssociatedObject(self, (void *)" + property_getter_name + ", rawValue, " + property_association_policy + "); }"

            return getter_func + "; " + setter_func
        else:
            # Only add methods if not readonly. Readonly properties do not
            # have a getter synthesized for them since ivars cannot be added.
            # The programmer is expected to implement the getter himself.
            return ""

    @classmethod
    def initializers(cls, property_obj):
        class_name = property_obj.class_.name
        logos_class_var = sigil("class", property_obj.group.name, class_name)
        readonly = property_obj.readonly
        retain = property_obj.retainFlag
        copy = property_obj.copyFlag
        nonatomic = property_obj.nonatomicFlag
        name = property_obj.name
        property_type = property_obj.type
        property_getter = property_obj.getter
        property_getter_name = cls.getterName(property_obj)
        property_setter = property_obj.setter
        property_setter_name = cls.setterName(property_obj)

        m = re.match(r'([^ *<]+).+', property_type)
        property_class_name = m.group(1) if m else property_type

        build = "{ objc_property_attribute_t _attributes[16]; unsigned int attrc = 0;"

        # Property attributes
        if retain:
            # Type encoding of object properties should be `@"ClassName"`
            build += cls.addAttribute("_attributes", "attrc", "T", '"@\\"' + property_class_name + '\\""')
            build += cls.addAttribute("_attributes", "attrc", "&")
        else:
            # Type encoding of non-object properties should be
            build += cls.addAttribute("_attributes", "attrc", "T", "@encode(" + property_type + ")")
        if readonly:
            build += cls.addAttribute("_attributes", "attrc", "R")

        if copy:
            build += cls.addAttribute("_attributes", "attrc", "C")
        if nonatomic:
            build += cls.addAttribute("_attributes", "attrc", "N")

        # class_addProperty
        build += " class_addProperty(" + logos_class_var + ", \"" + name + "\", _attributes, attrc);"

        # Only add methods if not readonly. Readonly properties do not
        # have a getter synthesized for them since ivars cannot be added.
        # The programmer is expected to implement the getter himself.
        if not readonly:
            build += " char _typeEncoding[1024];"
            # Getter
            build += ' snprintf(_typeEncoding, 1024, "%s@:", @encode(' + property_type + '));'
            build += " class_addMethod(" + logos_class_var + ", @selector(" + property_getter + "), (IMP)&" + property_getter_name + ", _typeEncoding);"

            # Setter
            build += ' snprintf(_typeEncoding, 1024, "v@:%s", @encode(' + property_type + '));'
            build += " class_addMethod(" + logos_class_var + ", @selector(" + property_setter + ":), (IMP)&" + property_setter_name + ", _typeEncoding);"

        build += " } "

        return build

