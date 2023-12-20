import models
import vk
import bot

import os
import sqlalchemy as sql
import sqlalchemy.orm as orm
import logging as log

from datetime import datetime
from time import sleep


def transmit_post(tg_token, post, sus, mirror: models.Mirror):
    tg_post = bot.send_post(tg_token, mirror.channel.tg_channel_id, post)
    post = models.Post(
        posted_datetime=datetime.fromtimestamp(post['date']),
        vk_post_id=post['id'],
        vk_owner_id=post['owner_id'],
        tg_post_id=tg_post['message_id'],
        mirror=mirror
    )
    sus.add(post)
    sus.commit()


def send_post_batch(vk_token, tg_token, sus, posts, mirror: models.Mirror):
    err_fmt = "Failed to transmit post [id={}, date={}, text={}...]"
    for post in posts:
        post_datetime = None
        text = post.get("text")
        if text is not None:
            text = text[:10]

        try:
            post_datetime = datetime.fromtimestamp(post.get('date'))
            transmit_post(tg_token, post, sus, mirror)
            mirror.start_datetime = post_datetime
            sus.commit()
        except Exception:
            log.error(err_fmt.format(post.get('id'), post_datetime, text))


def transmit_posts(vk_token, tg_token, sus, mirror: models.Mirror):
    ids = vk.fill_post_ids(
        vk_token,
        mirror.start_datetime,
        mirror.vk_group_id,
        mirror.vk_group_name
    )
    batch_size = vk.MAX_VK_POSTS_PER_REQUEST

    for i in range(0, len(ids), batch_size):
        j = min(i + batch_size, len(ids))
        posts = vk.get_posts_by_ids(vk_token, ids[i:j])
        send_post_batch(vk_token, tg_token, sus, posts, mirror)


def send_comment(vk_token, tg_token, chat_id, comment, reply_to=None):
    print("\n\n\n\n")
    print(
        f"Send comment args: chat_id={chat_id}, reply_to={reply_to}, comment={comment}")
    user = vk.get_user(vk_token, comment['from_id'])
    if not user:
        user = {}
    return bot.send_post(tg_token, chat_id, comment, reply_to=reply_to,
                         format_str="\\[[%s %s](vk.com/%s)\\] {}" % (
                             user.get('first_name'),
                             user.get('last_name'),
                             user.get('screen_name')
                         ),
                         parse_mode="MarkdownV2")


def transmit_comments_for_post(vk_token, tg_token, sus, post: models.Post):
    chname = post.mirror.channel.tg_channel_name
    if not post.tg_linked_chat_post_id:
        log.warn(f"Channel {chname} doesn't have linked chat")
        return

    channel = post.mirror.channel
    batch_size = 4
    comments = vk.get_comments(
        vk_token,
        post.vk_owner_id,
        post.vk_post_id,
        offset=post.comments_offset,
        count=batch_size,
        sort='desc',
    )
    log.debug(f"Got comments batch for channel {chname}")
    log.debug(f"Comments are {comments}")

    # post.comments_offset += len(comments)
    # sus.commit()
    for comment in comments:
        log.debug("Sending comment")
        tgcom = send_comment(vk_token, tg_token, channel.tg_linked_chat_id, comment,
                             reply_to=post.tg_linked_chat_post_id)
        if not tgcom:
            log.debug("Failed to send comment")
            continue
        log.debug("Sent comment")
        mcom = models.Comment(
            vk_comment_id=str(str(comment['id'])),
            tg_comment_id=str(str(tgcom['message_id'])),
            commented_datetime=datetime.fromtimestamp(comment['date']),
            post=post
        )
        sus.add(mcom)
        sus.commit()


def get_tg_reply_to_from_comment(
    sus,
    thread_comment,
    parent_comment: models.Comment
):
    vk_reply_to = str(thread_comment.get("reply_to_comment"))
    tg_reply_to = parent_comment.post.tg_linked_chat_post_id
    if vk_reply_to is not None:
        slct = sql.select(
            models.Comment
        ).where(
            models.Comment.vk_comment_id == vk_reply_to
        )
        real_parent = sus.scalars(slct).all()
        if real_parent:
            tg_reply_to = real_parent[0].tg_comment_id
    return tg_reply_to


def exists_comment(sus, vk_comment):
    slct = sql.select(
        models.Comment
    ).where(
        models.Comment.vk_comment_id == str(vk_comment['id'])
    )
    return len(sus.scalars(slct).all()) != 0


def transmit_thread_for_comment(vk_token, tg_token, sus, comment: models.Comment):
    thread_comments = vk.get_thread(vk_token, comment.post.vk_owner_id,
                                    comment.post.vk_post_id, comment.vk_comment_id)
    print("Thread comments:", thread_comments)
    channel = comment.post.mirror.channel
    for thread_comment in thread_comments:
        if exists_comment(sus, thread_comment):
            continue
        reply_to = get_tg_reply_to_from_comment(sus, thread_comment, comment)
        tgcom = send_comment(vk_token, tg_token, channel.tg_linked_chat_id, thread_comment,
                             reply_to=reply_to)
        if not tgcom:
            continue
        mcom = models.Comment(
            vk_comment_id=str(thread_comment['id']),
            tg_comment_id=str(tgcom['message_id']),
            commented_datetime=datetime.fromtimestamp(thread_comment['date']),
            post=comment.post
        )
        sus.add(mcom)
        sus.commit()


def transmit_threads_for_post(vk_token, tg_token, sus, post: models.Post):
    if not post.tg_linked_chat_post_id:
        return

    slct = sql.select(
        models.Comment
    ).where(
        models.Comment.post == post
    )
    comments = sus.scalars(slct)

    for comment in comments:
        transmit_thread_for_comment(vk_token, tg_token, sus, comment)


def transmit_comments_for_mirror(
    vk_token,
    tg_token,
    sus,
    mirror: models.Mirror
):
    slct = sql.select(
        models.Post
    ).where(
        models.Post.mirror == mirror
    ).order_by(
        models.Post.posted_datetime.desc()
    ).limit(4)
    posts = sus.scalars(slct)

    for post in posts:
        transmit_comments_for_post(vk_token, tg_token, sus, post)


def transmit_threads_for_mirror(
    vk_token,
    tg_token,
    sus,
    mirror: models.Mirror
):
    slct = sql.select(
        models.Post
    ).where(
        models.Post.mirror
    ).order_by(
        models.Post.posted_datetime.desc()
    ).limit(4)
    posts = sus.scalars(slct)

    for post in posts:
        transmit_threads_for_post(vk_token, tg_token, sus, post)


def load_mirrors_list(sus):
    mirrors = sus.execute(sql.select(models.Mirror)).scalars().all()
    return mirrors if mirrors else []


def mirror_mirrors(sus, vk_token, tg_token):
    mirrors = load_mirrors_list(sus)
    for mirror in mirrors:
        transmit_posts(vk_token, tg_token, sus, mirror)
        transmit_comments_for_mirror(vk_token, tg_token, sus, mirror)
        transmit_threads_for_mirror(vk_token, tg_token, sus, mirror)


def main(vk_token, tg_token, loglevel, echo_sql: bool):
    bot.setup_logging("mirror_engine_log.txt", loglevel)
    log.info("Mirror engine started")
    bot.init_db(echo_sql, create_scheme=False)
    log.info("Connected to database")

    while True:
        with orm.Session(models.engine) as sus:
            mirror_mirrors(sus, vk_token, tg_token)
        sleep(1)  # TODO: Change/remove


if __name__ == "__main__":
    try:
        main(os.getenv('VK_TOKEN'), os.getenv('TG_TOKEN'), "info", False)
    except KeyboardInterrupt:
        print("")
        exit(0)
