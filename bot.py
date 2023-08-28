import vk
import tg
import models
import mirror_engine

import sqlalchemy as sql
import sqlalchemy.orm as orm
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
    splits = s.split()
    return (splits[0][1:], splits[1:])


def help_command(vk_token, tg_token, msg):
    text = """
        This is help command.
    """
    tg.send_message(tg_token, msg['chat']['id'], text)


def get_post_command(vk_token, tg_token, msg, owner_id, domain, offset=0):
    post = vk.get_posts(vk_token, owner_id=owner_id, domain=domain,
                        count=1, offset=offset)[0]
    send_post(tg_token, msg['chat']['id'], post)


def add_mirror_command(vk_token, tg_token, msg,
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

    user_id = str(msg['from']['id'])

    with orm.Session(models.engine) as sus:
        slct = sql.select(models.User).where(
            models.User.tg_user_id == user_id
        )
        admin = sus.execute(slct).scalar()
        channel = None if not admin else next(
            filter(lambda ch: ch.tg_channel_id == tg_mirror_id,
                   admin.channels),
            None
        )
        if not channel:
            tg.send_message(tg_token,
                            msg['chat']['id'],
                            "You don't own this channel")
            return
        if channel.mirror:
            print("Mirror is:")
            print(channel.mirror)
            tg.send_message(
                tg_token,
                msg['chat']['id'],
                f"""
                    Existing mirror is already binded to this channel.
                    Use \"/delete_mirror {channel.mirror[0].id}\" to delete it.
                """
            )
            return

        mirror = models.Mirror(
            vk_group_id=vk_group_id,
            vk_group_name=vk_group_name,
            start_datetime=start_datetime,
            channel=channel
        )
        sus.add(mirror)
        sus.commit()


def list_mirrors_command(vk_token, tg_token, msg):
    text_list = ['List of mirrors:']
    mirror_text = '{}: {} -> {}\nLast mirrored post datetime: {}'

    with orm.Session(models.engine) as sus:
        mirrors = sus.execute(sql.select(models.Mirror)).scalars().all()
        for mirror in mirrors:
            formated_text = mirror_text.format(
                mirror.id,
                mirror.vk_group_name,
                mirror.channel.tg_channel_id,
                mirror.start_datetime.strftime("%d/%m/%Y %H:%M:%S")
            )
            text_list.append(formated_text)

    tg.send_message(tg_token, msg['chat']['id'], '\n'.join(text_list))


def list_channels_command(vk_token, tg_token, msg):
    user_id = str(msg['from']['id'])
    channels_desc = []
    desc_format = 'id: {}, name: {}'
    with orm.Session(models.engine) as sus:
        slct = sql.select(models.User).where(
            models.User.tg_user_id == user_id
        )
        admin = sus.execute(slct).scalar()
        if not admin:
            tg.send_message(tg_token,
                            msg['chat']['id'], "You don't own any channels")
            return
        for channel in admin.channels:
            channels_desc.append(
                desc_format.format(
                    channel.tg_channel_id, channel.tg_channel_name
                )
            )
    tg.send_message(
        tg_token, msg['chat']['id'], '\n'.join(channels_desc)
    )


def delete_mirror_command(vk_token, tg_token, msg, mirror_id):
    user_id = str(msg['from']['id'])

    with orm.Session(models.engine) as sus:
        slct = sql.select(models.User).where(
            models.User.tg_user_id == user_id
        )
        admin = sus.execute(slct).scalar()

        print("Lol")
        channel = None if not admin else next(
            filter(lambda ch: ch.mirror and str(ch.mirror[0].id) == mirror_id,
                   admin.channels),
            None
        )
        print("Kek")

        if not channel or not channel.mirror:
            tg.send_message(
                tg_token, msg['chat']['id'], "You don't own this mirror"
            )
        sus.delete(channel.mirror[0])
        sus.commit()
    tg.send_message(tg_token, msg['chat']['id'], "Deleted")


def get_chat_id_command(vk_token, tg_token, msg):
    tg.send_message(tg_token, msg['chat']['id'], f"{msg['chat']['id']}")


def get_my_id_command(vk_token, tg_token, msg):
    tg.send_message(tg_token, msg['chat']['id'],
                    f"{msg.get('from', {}).get('id')}")


def add_admin_command(vk_token, tg_token, msg, id):
    print(msg)
    channel_id = str(msg['chat']['id'])
    new_admin = models.User(tg_user_id=id)

    with orm.Session(models.engine) as sus:
        slct = sql.select(models.User).where(
            models.User.tg_user_id == id
        )
        admin = sus.execute(slct).scalar()

        if not admin:
            sus.add(new_admin)
            admin = new_admin

        new_channel = models.Channel(
            tg_channel_id=channel_id,
            tg_channel_name=msg['chat']['title'],
            users=[admin]
        )

        slct = sql.select(models.Channel).where(
            models.Channel.tg_channel_id == channel_id
        )
        channel = sus.execute(slct).scalar()

        if channel:
            channel.users.append(admin)
        else:
            channel = new_channel
            sus.add(channel)

        sus.commit()


def try_exec_text_msg(msg, vk_token, tg_token):
    commands = {
        'help': help_command,
        'get_post': get_post_command,
        'add_mirror': add_mirror_command,
        'list_mirrors': list_mirrors_command,
        'list_channels': list_channels_command,
        'delete_mirror': delete_mirror_command,
        'get_chat_id': get_chat_id_command,
        'get_my_id': get_my_id_command,
        'add_admin': add_admin_command
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
        "-m", "--mirror",
        help="enable mirror",
        action="store_true"
    )
    parser.add_argument(
        "--no-db", dest="no_db",
        help="don't connect to db",
        action="store_true"
    )
    parser.add_argument(
        "-l", "--load",
        metavar='FILE.env',
        help="load settings from FILE.env"
    )
    return parser.parse_args()


def main():
    args = setup_args()
    mirror_process = Process(
        target=mirror_engine.main,
        daemon=True
    )
    if args.load:
        load_dotenv(args.load)

    if not args.no_db:
        models.init(
            os.getenv('DB_USER'), os.getenv('DB_HOST'),
            os.getenv('DB_DB'), os.getenv('DB_PASSWORD'),
            os.getenv('DB_PORT', '6644')
        )
    if args.mirror:
        mirror_process.start()

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
