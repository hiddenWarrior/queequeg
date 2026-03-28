async def async_helper():
    return "async"


async def async_uses_helper():
    return await async_helper()
