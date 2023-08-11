import vk
import tg
import models

import sqlalchemy
import argparse
import datetime
import json
import os

from datetime import datetime
from collections import namedtuple
from dotenv import load_dotenv

# Globals TODO: Remove
mirrors = []

def send_post(token, chat_id, post):
    photos = extract_photos(post)
    gifs = extract_gifs(post)
    print(post)

    if photos and gifs:
        print("Too much media in one post")
        return
    
    if gifs:
        print('Has gifs!!!!')
        tg.send_animation(token, chat_id, gifs[0], caption=post['text'])
        return

    if not photos and not ('text' in post):
        return

    if not photos:
        tg.send_message(token, chat_id, post['text'])
        return

    if len(photos) == 1:
        tg.send_photo(token, chat_id, photos[0], caption=post['text']) 
        return 

    tg.send_multiphoto(token, chat_id, photos, caption=post['text'])

def extract_photo(photo_obj):
    bstw = 0 
    bsth = 0 
    bst_url = ""
    for scaled_photo in photo_obj['sizes']:
        w = scaled_photo['width']
        h = scaled_photo['height']
        if w > bstw or h > bsth: 
            w = bstw
            h = bsth
            bst_url = scaled_photo['url']
    return bst_url 

def extract_photos(post):
    photos = []
    for attachment in post['attachments']:
        if attachment['type'] == "photo":
            photos.append(extract_photo(attachment['photo']))
    return photos

def extract_gifs(post):
    gifs = []
    for attachment in post['attachments']:
        if attachment['type'] == 'doc' and attachment['doc']['ext'] == 'gif':
            gifs.append(attachment['doc']['url'])
    return gifs

def is_command(s):
    return s[0] == '/'

def parse_command(s):
    """
        Parse command from text
    Imput:
        s : str
    Output:
        (command_name, args) : tuple
        Where:
        command_name : str
        args : dict
    """
    splits = s.split()
    return (splits[0][1:], splits[1:])


def help_command(vk_token, tg_token, msg):
    text = """
        This is help command.
    """
    tg.send_message(tg_token, msg['chat']['id'], text)

def get_command(vk_token, tg_token, msg, owner_id, domain, offset=0):
    post = vk.get_posts(vk_token, owner_id=owner_id, domain=domain, 
                        count=1, offset=offset)[0]
    send_post(tg_token, msg['chat']['id'], post)

def create_command(vk_token, tg_token, msg, 
                   tg_mirror_id, vk_group_id, vk_group_name, 
                   start_date = None, start_time = None):
    date_format = "%Y/%m/%d"
    time_format = "%H:%M:%S" 
    start_datetime = None

    if start_date and start_time:
        start_datetime = start_date + ' ' + start_time
        start_datetime = datetime.strptime(start_datetime, 
                                           f"{date_format} {time_format}")
    elif start_date:
        start_datetime = datetime.strptime(start_date, date_format) 

    if not start_datetime: 
        start_datetime = datetime.now()

    mirror = models.Mirror(
        tg_mirror_id=tg_mirror_id,
        vk_group_id=vk_group_id,
        vk_group_name=vk_group_name,
        start_datetime=start_datetime
    )

    # Add mirror to database 
    with sqlalchemy.orm.Session(models.engine) as sus:
        sus.add(mirror)
        sus.commit()

def list_command(vk_token, tg_token, msg):
    chat_id = msg['chat']['id']
    text_list = ['List of mirrors:'] 
    mirror_text = '{}: {} -> {}\nLast mirrored post datetime: {}'

    for mirror in mirrors:
        formated_text = mirror_text.format(mirror.id, 
                                           mirror.vk_group_name, 
                                           mirror.tg_mirror_id,
                                           mirror.start_datetime.strftime("%d/%m/%Y %H:%M:%S"))
        text_list.append(formated_text)

    tg.send_message(tg_token, msg['chat']['id'], '\n'.join(text_list))

def delete_command(vk_token, tg_token, msg, mirror_id):
    mirror_id = int(mirror_id)
    with sqlalchemy.orm.Session(models.engine) as sus:
        mirror = sus.get(models.Mirror, mirror_id)
        sus.delete(mirror)
        sus.commit()

def getid_command(vk_token, tg_token, msg):
    print(msg)
    tg.send_message(tg_token, msg['chat']['id'], f"{msg['chat']['id']}")

def transmit_posts(vk_token, tg_token, mirror : models.Mirror):
    ids = vk.fill_post_ids(vk_token, mirror.start_datetime, 
                           mirror.vk_group_id, mirror.vk_group_name)
    ids_len = len(ids)
    last_post_datetime = None

    try:
        for i in range(0, len(ids), vk.MAX_VK_POSTS_PER_REQUEST):  
            j = min(i + vk.MAX_VK_POSTS_PER_REQUEST, len(ids)) 
            posts = vk.get_posts_by_ids(vk_token, ids[i:j]) 
            print(f"Loaded posts from {i + 1} to {j}")
            post_idx = i

            for post in posts:
                print(f"Transmission {post_idx}/{ids_len}")
                post_idx += 1
                if post:
                    send_post(tg_token, mirror.tg_mirror_id, post)
                    last_post_datetime = datetime.fromtimestamp(post['date'])
    except:
        return last_post_datetime
    return last_post_datetime

def send_posts_to_mirrors(vk_token, tg_token):
    global mirrors  

    for mirror in mirrors:
        new_start_datetime = transmit_posts(vk_token, tg_token, mirror)
        if not new_start_datetime:
            continue

        with sqlalchemy.orm.Session(models.engine) as sus:
            sus_mirror = sus.get(models.Mirror, mirror.id)
            sus_mirror.start_datetime = new_start_datetime
            sus.commit()

def refresh_mirrors_list():
    global mirrors

    with sqlalchemy.orm.Session(models.engine) as sus:
        mirrors = sus.execute(sqlalchemy.select(models.Mirror)).scalars().all()

    print("Got mirrors:")
    print(mirrors)

def try_exec_text_msg(msg, vk_token, tg_token):
    commands = { 
                'help' : help_command, 
                'get' : get_command,
                'create' : create_command,
                'list' : list_command,
                'delete' : delete_command,
                'getid' : getid_command
               }
    text = msg['text'].strip()
    if not is_command(text):
        return 
    
    command_name, args = parse_command(text)
    if command_name not in commands:
        return
    try:
        commands[command_name](vk_token, tg_token, msg, *args)
    except Exception as e:
        print(f'Command "{command_name}" failed, args={args}')
        print(f'Thrown exception:\n{e}')

def process_updates(updates, vk_token, tg_token):
    for update in updates: 
        if 'message' in update and 'text' in update['message']: 
            try_exec_text_msg(update['message'], vk_token, tg_token)
        elif 'channel_post' in update:
            try_exec_text_msg(update['channel_post'], vk_token, tg_token)

def setup_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--mirror", help="enable mirror", action="store_true")
    parser.add_argument("-l", "--load", metavar='FILE.env',
                        help="load settings from FILE.env")
    return parser.parse_args()

def main():
    args = setup_args()

    if args.load:
        load_dotenv(args.load) 

    models.init(os.getenv('DB_USER'), os.getenv('DB_HOST'), 
                os.getenv('DB_DB'), os.getenv('DB_PASSWORD'),
                os.getenv('DB_PORT', '6644'))

    vk_token = os.getenv('VK_TOKEN')
    tg_token = os.getenv('TG_TOKEN')
    if vk_token is None:
        print('Missing vk token in env')
        exit(0)
    if tg_token is None:
        print('Missing tg token in env')
        exit(0)

    offset = None 

    while True:
        if args.mirror:
            refresh_mirrors_list()
            send_posts_to_mirrors(vk_token, tg_token)

        updates = tg.get_tg_updates(tg_token, offset)
        if updates:
            offset = updates[-1]['update_id'] + 1
            process_updates(updates, vk_token, tg_token)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("")
        exit(0)

# TODO: support multiple photos, gifs, video

