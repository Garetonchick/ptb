import vk
import tg
import models
import mirror_engine

import sqlalchemy as sql
import sqlalchemy.orm as orm
import argparse
import logging as log
import os

from datetime import datetime
from dotenv import load_dotenv
from multiprocessing import Process


def send_post(token, chat_id, post, reply_to=None, parse_mode=None,
              format_str="{}"):
    photos = vk.extract_photos(post)
    gifs = vk.extract_gifs(post)
    text = format_str.format(post['text'])

    if photos and gifs:
        log.warning(
            f"""
            Post {post.get('id')} of owner {post.get('owner_id')}
            had too much media and was ommited
            """
        )
        return None

    if gifs:
        msg = tg.send_animation(token, chat_id, gifs[0], caption=text,
                                reply_to=reply_to, parse_mode=parse_mode)
        return msg

    if not photos and not ('text' in post):
        return None

    if not photos:
        msg = tg.send_message(token, chat_id, text, reply_to=reply_to,
                              parse_mode=parse_mode)
        return msg

    if len(photos) == 1:
        msg = tg.send_photo(token, chat_id, photos[0], caption=text,
                            reply_to=reply_to, parse_mode=parse_mode)
        return msg

    return tg.send_multiphoto(token, chat_id, photos, caption=text,
                              reply_to=reply_to, parse_mode=parse_mode)


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

        channel = None if not admin else next(
            filter(lambda ch: ch.mirror and str(ch.mirror[0].id) == mirror_id,
                   admin.channels),
            None
        )

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


def link_chat_command(vk_token, tg_token, msg, channel_id):
    chat_id = str(msg['chat']['id'])

    with orm.Session(models.engine) as sus:
        slct = sql.select(models.Channel).where(
            models.Channel.tg_channel_id == channel_id
        )
        channel = sus.execute(slct).scalar()

        if not channel:
            tg.send_message(
                tg_token, msg['chat']['id'], "You don't own this channel"
            )
            return

        channel.tg_linked_chat_id = chat_id
        sus.commit()


def try_link_post(msg):
    channel_post_id = str(msg['forward_from_message_id'])
    with orm.Session(models.engine) as sus:
        slct = sql.select(models.Post).where(
            models.Post.tg_post_id == channel_post_id
        )
        posts = sus.scalars(slct).all()
        if posts:
            posts[0].tg_linked_chat_post_id = str(msg['message_id'])
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
        'add_admin': add_admin_command,
        'link_chat': link_chat_command
    }
    text = msg['text'].strip()
    if not is_command(text):
        return

    command_name, args = parse_command(text)
    if command_name not in commands:
        return
    try:
        commands[command_name](vk_token, tg_token, msg, *args)
    except Exception:
        log.error(f"Command '{command_name}' failed, args={args}")
        raise


def process_message(msg, vk_token, tg_token):
    if 'is_automatic_forward' in msg:
        try_link_post(msg)
    elif 'text' in msg:
        try_exec_text_msg(msg, vk_token, tg_token)


def process_channel_post(post, vk_token, tg_token):
    try_exec_text_msg(post, vk_token, tg_token)


def process_update(update, vk_token, tg_token):
    try:
        if 'message' in update:
            process_message(update['message'], vk_token, tg_token)
        elif 'channel_post' in update:
            process_channel_post(update['channel_post'], vk_token, tg_token)
    except Exception:
        log.exception("Update handling failed. Raised exception:")


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
        "--echo_sql", dest="echo_sql",
        help="Echo sql queries",
        action="store_true"
    )
    parser.add_argument(
        "-l", "--load",
        metavar='FILE.env',
        help="load settings from FILE.env"
    )
    parser.add_argument(
        "--log",
        metavar='LEVEL',
        help="log events with logging level LEVEL",
        default="INFO"
    )
    return parser.parse_args()


def setup_logging(logfile, loglevel: str):
    loglevel_num = getattr(log, loglevel.upper(), None)
    if not isinstance(loglevel_num, int):
        raise ValueError('Invalid log level: %s' % loglevel)
    log.basicConfig(
        filename=logfile,
        filemode="w",
        level=loglevel
    )


def start_mirror_engine(vk_token, tg_token, args):
    mirror_process = Process(
        target=mirror_engine.main,
        args=(vk_token, tg_token, args.log, args.echo_sql),
        daemon=True
    )
    mirror_process.start()


def init_db(echo_sql=False, create_scheme=True):
    try:
        models.init(
            os.getenv('DB_USER'), os.getenv('DB_HOST'),
            os.getenv('DB_DB'), os.getenv('DB_PASSWORD'),
            os.getenv('DB_PORT', '6644'),
            echo=echo_sql
        )
    except Exception:
        log.error("Failed to connect to db")
        raise


def getenv_or_raise(name: str):
    env = os.getenv(name)
    if env is None:
        raise ValueError(
            "Missing \"{}\" environment variable".format(name)
        )
    return env


def main():
    args = setup_args()
    setup_logging("bot_log.txt", args.log)

    if args.load:
        load_dotenv(args.load)

    vk_token = getenv_or_raise('VK_TOKEN')
    tg_token = getenv_or_raise('TG_TOKEN')

    if not args.no_db:
        init_db(bool(args.echo_sql))
        log.info("Connected to database")

    if args.mirror:
        start_mirror_engine(vk_token, tg_token, args)
        log.info("Started mirror engine")

    tg.poll_tg_updates(
        lambda update: process_update(update, vk_token, tg_token),
        tg_token
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Recieved KeyboardInterrupt")
        print("")
        exit(0)
