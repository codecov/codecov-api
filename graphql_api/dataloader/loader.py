from aiodataloader import DataLoader
from asgiref.sync import sync_to_async


class BaseLoader(DataLoader):
    @classmethod
    def loader(cls, info, *args):
        """
        Creates a new loader for the given `info` (instance of GraphQLResolveInfo) and `args`.
        If a loader of this type already exists for the given `args` then that same object will
        be returned from the request context.
        """
        context_key = f"__dataloader_{cls.__name__}"
        if len(args) > 0:
            args_key = "_".join([str(arg) for arg in args])
            context_key += f"_{args_key}"

        if context_key not in info.context:
            # one loader of a given (type, args) per request
            info.context[context_key] = cls(*args)

        return info.context[context_key]

    @classmethod
    def key(cls, record):
        """
        Return the cache key for the given record (defaults to `id`)
        """
        return record.id

    def cache(self, record):
        """
        Prime the cache with the given record
        """
        self.prime(self.key(record), record)

    def batch_queryset(self, keys):
        """
        Return an unordered QuerySet that includes a record for every key in `keys`.
        (ordering is handled in `batch_load_fn`)
        """
        raise NotImplementedError("override batch_queryset in subclass")

    @sync_to_async
    def batch_load_fn(self, keys):
        """
        This implements the aiodataloader interface to batch load records for an
        ordered list of keys.

        Each time we call `load` in the same tick of the event loop, aiodataloader
        remembers the load key and defers the results.  At the end of the tick we
        batch load the records for all those keys.
        """

        queryset = self.batch_queryset(keys)
        results = {self.key(record): record for record in queryset}

        # the returned list of records must be in the exact order of `keys`
        return [results.get(key) for key in keys]
