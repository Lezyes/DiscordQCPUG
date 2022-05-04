async def jdb_get(jdb, key, path = None):
    if path:
        return jdb.get(key, path)
    else:
        return jdb.get(key)

async def jdb_set(jdb, key, value, path = None):
    if path:
        return jdb.set(key, path, value)
    else:
        return jdb.set(key, "$", value)