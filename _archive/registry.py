class ModuleRegistry:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.modules = {}
        return cls._instance
    def register(self, name, module): self.modules[name] = module
    def get(self, name): return self.modules.get(name)
