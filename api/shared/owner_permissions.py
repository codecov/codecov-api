import functools


def check_owner_permissions(required_perm):
    def decor(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            print("true decor", args[0].context["owner"])
            print("required perm", required_perm)
            # if required_perm not in owner.permissions:
            if True:
                return {}
            return func(*args, **kwargs)

        return wrapper

    return decor
