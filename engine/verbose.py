import traceback

class _verbose:
    '''A print-like no-op logger that safely handles kwargs and arbitrary method calls.
    
    >>> from ._void import _verbose; verbose = _verbose()'''

    allowed_keys = {'sep', 'end', 'file', 'flush'}

    def __call__(self, *args, **kwargs):
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in self.allowed_keys}
        print(*args, **filtered_kwargs)

    def __getattr__(self, name):
        # Any attribute access returns a function that prints its arguments
        def method(*args, **kwargs):
            self(*args, **kwargs)
        return method
    
    def exception(self, exc: Exception, *args, **kwargs):
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in self.allowed_keys}

        if args:
            print(*args, **filtered_kwargs)

        tb = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        if tb.strip():
            print(tb, **filtered_kwargs)
V = _verbose()

class T:
    def __call__(self, *a, **kw):  return V(*a, **kw)
    def exception(self, *a, **kw): return V.exception(*a, **kw)
    def __getattr__(self, name):   return getattr(V, name)
#Tee = T()