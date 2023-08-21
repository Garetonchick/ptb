import models
import vk
import bot

import os
import sqlalchemy as sql
import sqlalchemy.orm as orm

from datetime import datetime
from time import sleep


def transmit_posts(vk_token, tg_token, mirror: models.Mirror):
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
                    bot.send_post(tg_token, mirror.tg_mirror_id, post)
                    last_post_datetime = datetime.fromtimestamp(post['date'])
    except:
        return last_post_datetime
    return last_post_datetime


def load_mirrors_list():
    mirrors = []
    with orm.Session(models.engine) as sus:
        mirrors = sus.execute(sql.select(models.Mirror)).scalars().all()
    return mirrors if mirrors else []


def mirror_mirrors(mirrors, vk_token, tg_token):
    for mirror in mirrors:
        new_start_datetime = transmit_posts(vk_token, tg_token, mirror)
        if not new_start_datetime:
            continue

        with orm.Session(models.engine) as sus:
            sus_mirror = sus.get(models.Mirror, mirror.id)
            sus_mirror.start_datetime = new_start_datetime
            sus.commit()


def main():
    print("Mirror engine started")
    vk_token = os.getenv('VK_TOKEN')
    tg_token = os.getenv('TG_TOKEN')

    if not vk_token:
        print('Missing vk token in env')
        exit(0)
    if not tg_token:
        print('Missing tg token in env')
        exit(0)

    models.init(os.getenv('DB_USER'), os.getenv('DB_HOST'),
                os.getenv('DB_DB'), os.getenv('DB_PASSWORD'),
                os.getenv('DB_PORT', '6644'), create_scheme=False)
    while True:
        mirrors = load_mirrors_list()
        mirror_mirrors(mirrors, vk_token, tg_token)
        sleep(1)  # TODO: Change/remove


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("")
        exit(0)
