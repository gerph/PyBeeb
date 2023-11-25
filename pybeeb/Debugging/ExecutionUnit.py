

class LoggingExecutionUnit(object):
    def __init__(self):
        pass

    def __getattr__(self, name):
        def handler(*args, **kwargs):
            print "%s called (%s, %s)" % (name, args, kwargs)
        return handler
