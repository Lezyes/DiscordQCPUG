
from PIL import Image, ImageOps
from functools import reduce
from io import BytesIO
import requests
from uuid import uuid4
import os

def clear_img(img, thresh = 180):
    fn = lambda x : 255 if x > thresh else 0
    r = img.convert('L').point(fn, mode='1')
    return ImageOps.invert(r)

def crop_player_names(img, thresh = 180):
    imgs = []
    width, height = img.size
    pos_list = [
        (0.208, 0.175), # left top left
        (0.265, 0.340), # left top right
        (0.776, 0.065), # left bottom left
        (0.838, 0.275), # left bottom right
        
        
        (0.267, 0.558), # right top left
        (0.208, 0.725), # right top right
        (0.838, 0.625), # right bottom left
        (0.772, 0.830), # right bottom right        
               ]     
    
    
    #[(top,left)]
    for top_pos_precent, left_pos_precent in pos_list:
        top = height * top_pos_precent
        bottom = top + height*0.0225
        left = width * left_pos_precent
        right = left + width*0.105
        imgs.append(clear_img(img.crop((left, top, right, bottom)),thresh = thresh))
    return imgs

def get_concat_v(im1, im2):
    dst = Image.new('RGB', (im1.width, im1.height + im2.height))
    dst.paste(im1, (0, 0))
    dst.paste(im2, (0, im1.height))
    return dst

def crop_game_mode(img):
    width, height = img.size

    top_pos_precent = 0.10
    left_pos_precent = 0.42

    top = height * top_pos_precent
    bottom = top + height*0.03
    left = width * left_pos_precent
    right = left + width*0.15

    mode_name= img.crop((left, top, right, bottom))
    return clear_img(mode_name)

async def process_image(url):
    response = requests.get(url)
    input_img = Image.open(BytesIO(response.content))

    game_mode_img = crop_game_mode(input_img)
    player_names_imgs = crop_player_names(input_img, thresh = 120)
    player_names_img = reduce(get_concat_v, player_names_imgs)
    
    game_mode_img_name = "{}.jpg".format(str(uuid4()))
    game_mode_img_path = os.path.join("/data/",game_mode_img_name)
    
    player_names_img_name = "{}.jpg".format(str(uuid4()))
    player_names_img_path = os.path.join("/data/",player_names_img_name)

    game_mode_img.save(game_mode_img_path)
    player_names_img.save(player_names_img_path)
    return {"player_names_img_path":player_names_img_path,
            "game_mode_img_path":game_mode_img_path}
    
