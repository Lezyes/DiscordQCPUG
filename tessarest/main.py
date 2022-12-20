from typing import Union

from fastapi import FastAPI
from quake_ocr import process_image

import os
import subprocess

app = FastAPI()


@app.get("/")
async def read_root():
    return {"Nope": "you forgot, didn't you? :^)"}


@app.get("/qcocr/")
async def qcocr(url: str):
    images = await process_image(url)
    print(images)
    player_names_img_path = images.get("player_names_img_path")
    game_mode_img_path = images.get("game_mode_img_path")
    players_names_cmd = f"tesseract {player_names_img_path} stdout --oem 1"
    game_mode_cmd = f"tesseract {game_mode_img_path} stdout --oem 1"

    players_names = subprocess.check_output(players_names_cmd, shell = True).splitlines()
    game_mode = subprocess.check_output(game_mode_cmd, shell = True).splitlines()

    os.remove(player_names_img_path)
    os.remove(game_mode_img_path)
    return {"players_names": players_names, "game_mode": game_mode}

