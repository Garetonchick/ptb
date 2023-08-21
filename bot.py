import vk
import tg
import models
import mirror_engine

import sqlalchemy
import argparse
import os

from datetime import datetime
from dotenv import load_dotenv
from multiprocessing import Process


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
    bstw = photo_obj.get('width', 0)
    bsth = photo_obj.get('height', 0)
    bst_url = ""
    for scaled_photo in photo_obj['sizes']:
        w = scaled_photo['width']
        h = scaled_photo['height']
        if w >= bstw and h >= bsth:
            bstw = w
            bsth = h
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
                   start_date=None, start_time=None):
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
    text_list = ['List of mirrors:']
    mirror_text = '{}: {} -> {}\nLast mirrored post datetime: {}'
    mirrors = mirror_engine.load_mirrors_list()

    for mirror in mirrors:
        formated_text = mirror_text.format(
            mirror.id,
            mirror.vk_group_name,
            mirror.tg_mirror_id,
            mirror.start_datetime.strftime("%d/%m/%Y %H:%M:%S")
        )
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


def try_exec_text_msg(msg, vk_token, tg_token):
    commands = {
        'help': help_command,
        'get': get_command,
        'create': create_command,
        'list': list_command,
        'delete': delete_command,
        'getid': getid_command
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
    parser.add_argument(
        "-m", "--mirror", help="enable mirror", action="store_true")
    parser.add_argument("-l", "--load", metavar='FILE.env',
                        help="load settings from FILE.env")
    return parser.parse_args()


def main():
    args = setup_args()
    mirror_process = Process(target=mirror_engine.main, daemon=True)

    if args.load:
        load_dotenv(args.load)

    if args.mirror:
        mirror_process.start()

    models.init(os.getenv('DB_USER'), os.getenv('DB_HOST'),
                os.getenv('DB_DB'), os.getenv('DB_PASSWORD'),
                os.getenv('DB_PORT', '6644'))

    vk_token = os.getenv('VK_TOKEN')
    tg_token = os.getenv('TG_TOKEN')
    if not vk_token:
        print('Missing vk token in env')
        exit(0)
    if not tg_token:
        print('Missing tg token in env')
        exit(0)
    print(f"VK token: {vk_token}\nTG token: {tg_token}")

    offset = None

    while True:
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
