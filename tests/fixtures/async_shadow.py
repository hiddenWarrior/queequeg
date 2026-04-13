from tests.fixtures.cross_file_b import shared_helper


async def async_for_shadow():
    # async for loop var named 'shared_helper' — shadows the import, NOT a dep
    async for shared_helper in some_aiter():
        pass


async def async_with_shadow():
    # async with var named 'shared_helper' — shadows the import, NOT a dep
    async with some_ctx() as shared_helper:
        pass
