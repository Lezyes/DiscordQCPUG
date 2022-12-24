async def jdb_get(jdb, key, path = None):
    if path:
        return jdb.get(key, path)
    else:
        return jdb.get(key)

async def jdb_get_first(jdb, key, path):
    if path:
        item = jdb.get(key, path)
        if item:
            return item[0]
        else:
            return item

async def jdb_set(jdb, key, value, path = None):
    if path:
        return jdb.set(key, path, value)
    else:
        return jdb.set(key, "$", value)