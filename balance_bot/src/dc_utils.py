
async def clean_up_msg(data_dict):
    if data_dict["clean_up"]:
        await data_dict["thread"].delete()
        await data_dict["message"].delete()

async def get_thread_state(thread):
    pass
    # instaed of carrying all the data in data dict, data will be collected from the thread 
