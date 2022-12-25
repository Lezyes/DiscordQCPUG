import logging
logging.basicConfig(level=logging.WARNING)

def log(msg,level=None, *args, **kwargs):
    if level is None:
        level = logging.getLogger().level
    return logging.log(level, msg, *args, **kwargs)

    