
async def clean_up_msg(data_dict):
    if data_dict["clean_up"]:
        await data_dict["thread"].delete()
        await data_dict["message"].delete()
