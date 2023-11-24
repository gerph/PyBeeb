class Dispatcher(object):
    def __init__(self, executors):
        self.executors = executors

    def __getattr__(self, name):
        def handler(*args, **kwargs):
            for e in self.executors:
                fn = getattr(e,name)
                value = fn(*args, **kwargs)
            return value
        return handler