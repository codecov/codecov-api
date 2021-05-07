def wrap_error_handling_mutation(resolver):
    async def resolver_with_error_handling(*args, **kwargs):
        try:
            return await resolver(*args, **kwargs)
        except Exception as e:
            return {"error": str(e)}

    return resolver_with_error_handling
