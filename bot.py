import vk
import tg

import argparse
import datetime
import json
import os

from datetime import datetime
from dotenv import load_dotenv

# Globals TODO: Remove
smpm_id = '171296758'
smpm_domain = 'publicepsilon777'
db_path = os.getenv('DB_PATH', 'db.json')
start_transmitting_date = datetime(year=2023, month=5, day=1, 
                                   hour=0, minute=0, second=0)

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

def transmit_posts(vk_token, tg_token, start_date, vk_group_id, vk_group_domain, tg_mirror_id):
    global start_transmitting_date
    ids = vk.fill_post_ids(vk_token, start_date, vk_group_id, vk_group_domain)
    ids_len = len(ids)

    for i in range(0, len(ids), vk.MAX_VK_POSTS_PER_REQUEST):  
        j = min(i + vk.MAX_VK_POSTS_PER_REQUEST, len(ids)) 
        posts = vk.get_posts_by_ids(vk_token, ids[i:j]) 
        print(f"Loaded posts from {i + 1} to {j}")
        post_idx = i

        for post in posts:
            print(f"Transmission {post_idx}/{ids_len}")
            post_idx += 1
            if post:
                send_post(tg_token, tg_mirror_id, post)
                start_transmitting_date = datetime.fromtimestamp(post['date'])
                commit_changes_to_db()

def datetime_to_dict(dt):
    return { 'year' : dt.year, 'month' : dt.month, 'day' : dt.day, 'hour' : dt.hour, 'minute' : dt.minute, 'second' : dt.second }

def dict_to_datetime(d):
    return datetime(year=d['year'], month=d['month'], day=d['day'], hour=d['hour'], minute=d['minute'], second=d['second']) 

def commit_changes_to_db():
    global db_path, start_transmitting_date
    with open(db_path, 'w') as db:
        json.dump(datetime_to_dict(start_transmitting_date), db)

def load_from_db():
    global db_path, start_transmitting_date
    db = None
    try:
        db = open(db_path, 'r')
        start_transmitting_date = dict_to_datetime(json.load(db))
    except Exception as e:
        print("Falling back to default start_transmitting_date")
        print(e)
    finally:
        if db is not None:
            db.close()

def try_exec_text_msg(msg, vk_token, tg_token):
    commands = { 'help' : help_command, 'get' : get_command }
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

    global start_transmitting_date, smpm_id, smpm_domain

    vk_token = os.getenv('VK_TOKEN')
    tg_token = os.getenv('TG_TOKEN')
    mirror_id = os.getenv('MIRROR_ID')
    if vk_token is None:
        print('Missing vk token in env')
        exit(0)
    if tg_token is None:
        print('Missing tg token in env')
        exit(0)
    if args.mirror and not mirror_id:  
        print('Missing mirror id in env')
        exit(0)

    offset = None 

    load_from_db();

    while True:
        if args.mirror:
            transmit_posts(vk_token, tg_token, 
                           start_transmitting_date, smpm_id, smpm_domain, mirror_id)

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
