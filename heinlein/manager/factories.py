from heinlein.manager.factory import DataFactory
from heinlein.manager.manager import Manager

class FileFactory(DataFactory):

    def __init__(self, manager: Manager, *args, **kwargs):
        handlers = self.load_handlers()
        super().__init__(manager = manager, handlers = handlers)
    
    def load_handlers(self, *args, **kwargs):
        from heinlein.dtypes import get_file_handlers
        return get_file_handlers()

    def get_data(self, dtype, query_region, *args, **kwargs):
        path = self.manager.get_path(dtype)
        try:
            handler = self.handlers[dtype]
        except KeyError:
            raise AttributeError(f"Handlers object has no handler for dtype \'{dtype}\'")
        if not self.valid:
            raise AttributeError(f"Handler object must call \'verify\' method before use.")
        data = handler(path, query_region, *args, **kwargs)
        return data
