from .group import Group


class StaticClassGroup(Group):
    _logos_name = "StaticClassGroup"

    def __init__(self):
        super().__init__()
        self.name = "_staticClass"
        self.explicit = 0
        self.declaredOnlyClasses = {}
        self.usedClasses = {}
        self.usedMetaClasses = {}
        self._unescaped_names = {}

    def addUsedClass(self, cls, unescaped_class_name):
        if cls not in self.usedClasses:
            self.usedClasses[cls] = 0
        self.usedClasses[cls] += 1
        self._unescaped_names[cls] = unescaped_class_name

    def addUsedMetaClass(self, cls, unescaped_class_name):
        if cls not in self.usedMetaClasses:
            self.usedMetaClasses[cls] = 0
        self.usedMetaClasses[cls] += 1
        self._unescaped_names[cls] = unescaped_class_name

    def addDeclaredOnlyClass(self, cls):
        if cls not in self.declaredOnlyClasses:
            self.declaredOnlyClasses[cls] = 0
        self.declaredOnlyClasses[cls] += 1

    def unescapedClassNameForClass(self, cls):
        return self._unescaped_names.get(cls)
