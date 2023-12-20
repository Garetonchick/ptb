import requests
import json
import time
import logging as log

from datetime import datetime
from urllib.parse import quote as encode_url

MAX_VK_POSTS_PER_REQUEST = 100


def send_vk_api_request_impl(name, args, version):
    req_url = 'https://api.vk.com/method/' + name + '?'
    for arg_name, val in args.items():
        if val:
            req_url += '{}={}&'.format(arg_name, encode_url(str(val)))
    req_url += 'v=' + version
    try:
        resp = requests.get(req_url)
    except Exception:
        return None

    return resp


def send_vk_api_request(name, args, version='5.131'):
    while True:
        resp = send_vk_api_request_impl(name, args, version)

        if resp is None:
            return None

        resp_dict = json.loads(resp.text)
        error = None

        if resp.status_code == 200:
            error = resp_dict.get('error')

        if resp.status_code == 429 or (error and error.get('error_code', -1) == 6):
            print("Too many requests to vk api. Retrying...")
            time.sleep(0.4)
            continue

        if resp.status_code == 200:
            print("Response is: ", resp.text)
            return json.loads(resp.text).get('response')

        print(f"Bad request to vk api. Response code {resp.status_code}")
        break
    return None


def get_posts(token, owner_id='1', domain='apiclub', offset=0, count=1, flt='all'):
    resp = send_vk_api_request('wall.get', {'access_token': token, 'owner_id': '-' +
                               owner_id, 'domain': domain, 'offset': offset, 'count': count, 'filter': flt})
    return resp['items'] if resp else []


def get_user(token, user_id):
    resp = send_vk_api_request('users.get', {
        'access_token': token,
        'user_ids': user_id,
        'fields': "screen_name"
    })
    return resp[0] if resp and len(resp) else None


def get_comments(
        token,
        owner_id,
        post_id,
        offset=0,
        count=1,
        start_comment_id=None,
        sort='asc',
        thread_items_count=0,
        preview_length=0
):
    print("Getting comments")
    log.debug(f"get_comments owner_id={owner_id}, post_id={post_id}")
    resp = send_vk_api_request('wall.getComments', {
        'access_token': token,
        'owner_id': owner_id,
        'post_id': post_id,
        'offset': offset,
        'count': count,
        'start_comment_id': start_comment_id,
        'sort': sort,
        'thread_items_count': thread_items_count,
        'preview_length': preview_length
    })
    return resp['items'] if resp else []


def get_thread(
        token,
        owner_id,
        post_id,
        comment_id,
        sort='asc',
):
    print("get_comments", f"owner_id={owner_id}, post_id={post_id}")
    resp = send_vk_api_request('wall.getComments', {
        'access_token': token,
        'owner_id': owner_id,
        'post_id': post_id,
        'start_comment_id': comment_id,
        'sort': sort,
        'thread_items_count': 10,
        'preview_length': 0
    })
    res = None
    if resp:
        res = resp.get('items')
    if res:
        res = res[0].get('thread')
    if res:
        res = res.get('items')
    return res if res else []


def extract_id(post):
    return '{}_{}'.format(post['owner_id'], post['id'])


def fill_post_ids(vk_token, start_date, vk_group_id, vk_group_domain):
    ids = []
    bucket_size = 1
    offset = 1

    while True:
        bucket = get_posts(
            vk_token, owner_id=vk_group_id,
            domain=vk_group_domain, count=bucket_size, offset=offset
        )
        if not bucket:
            break

        bucket_ids = list(map(extract_id, bucket))

        if datetime.fromtimestamp(bucket[-1]['date']) <= start_date:
            bad_idx = next(filter(lambda x: datetime.fromtimestamp(
                x[1]['date']) <= start_date, enumerate(bucket)))[0]
            ids += bucket_ids[:bad_idx]
            offset += bad_idx
            break

        if ids and ids[-1] in bucket_ids:
            skip = bucket_ids.index(ids[-1]) + 1
            ids += bucket_ids[skip:]
        else:
            ids += bucket_ids
        offset += len(bucket)
        bucket_size = min(MAX_VK_POSTS_PER_REQUEST, bucket_size * 2)

    ids.reverse()
    return ids


def get_posts_by_ids(token, ids):
    global MAX_VK_POSTS_PER_REQUEST
    posts = []

    for i in range(0, len(ids), MAX_VK_POSTS_PER_REQUEST):
        bucket_size = min(len(ids) - i, MAX_VK_POSTS_PER_REQUEST)
        ids_for_url = ','.join(ids[i:i+bucket_size])
        resp = send_vk_api_request(
            'wall.getById', {'access_token': token, 'posts': ids_for_url})

        if resp:
            posts += resp

    return posts


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
    for attachment in post.get('attachments', []):
        if attachment['type'] == "photo":
            photos.append(extract_photo(attachment['photo']))
    return photos


def extract_gifs(post):
    gifs = []
    for attachment in post.get('attachments', []):
        if attachment['type'] == 'doc' and attachment['doc']['ext'] == 'gif':
            gifs.append(attachment['doc']['url'])
    return gifs
