import functools


def check_owner_permissions(required_perm):
    def decor(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            print("required", required_perm)
            print("allowed", args[0].context["owner_permissions"])
            if required_perm not in args[0].context["owner_permissions"]:
                return {}
            return func(*args, **kwargs)

        return wrapper

    return decor
