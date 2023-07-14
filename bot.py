import datetime
import requests
import json
import time
import os

from urllib.parse import quote as encode_url
from datetime import datetime

def send_vk_api_request_impl(name, args, version):
    req_url = 'https://api.vk.com/method/' + name + '?'
    for arg_name, val in args.items():
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

        if resp.status_code == 200:
            return json.loads(resp.text)['response']

        if resp.status_code == 429:
            print("Too many requests to vk api. Retrying...")
            time.sleep(0.4) 
        else:
            print(f"Bad request to vk api. Response code {resp.status_code}")
            break
    return None
    

def send_tg_api_request_impl(name, token, args):
    req_url = 'https://api.telegram.org/bot' + token + '/' + name + '?'
    for arg_name, val in args.items():
        if val:
            req_url += '{}={}&'.format(arg_name, encode_url(str(val)))

    req_url = req_url[:-1]
    try:
        resp = requests.get(req_url)
    except Exception:
        return None

    return resp

def send_tg_api_request(name, token, args):
    while True:
        resp = send_tg_api_request_impl(name, token, args)

        if resp is None:
            return None

        if resp.status_code == 200:
            return json.loads(resp.text)['result']

        if resp.status_code == 429:
            print("Too many requests to tg api. Retrying...")
            time.sleep(0.4) 
        else:
            print(f"Bad request to tg api. Response code {resp.status_code}")
            break
    return None


def get_posts(token, owner_id='1', domain='apiclub', offset=0, count=1, flt='all'): 
    resp = send_vk_api_request('wall.get', {'access_token' : token, 'owner_id' : '-' + owner_id, 'domain' : domain, 'offset' : offset, 'count' : count, 'filter' : flt})
    return resp['items'] if resp else [] 

def get_posts_by_ids(token, ids): 
    global MAX_VK_POSTS_PER_REQUEST
    posts = [] 

    for i in range(0, len(ids), MAX_VK_POSTS_PER_REQUEST):
        bucket_size = min(len(ids) - i, MAX_VK_POSTS_PER_REQUEST)
        ids_for_url = ','.join(ids[i:i+bucket_size])
        resp = send_vk_api_request('wall.getById', {'access_token' : token, 'posts' : ids_for_url})
        
        if resp:
            posts += resp

    return posts 

def get_tg_updates(token, offset = None, limit = 100, timeout = 1, allowed_updates=None):
    return send_tg_api_request('getUpdates', token, { 'offset' : offset, 'limit' : limit, 'timeout' : timeout, 'allowed_updates' : allowed_updates }) 

def send_message(token, chat_id, text, parse_mode=None):
    return send_tg_api_request('sendMessage', token, { 'chat_id' : chat_id, 'text' : text, 'parse_mode' : parse_mode }) is not None 

def send_photo(token, chat_id, photo_url, caption=None, parse_mode=None):
    return send_tg_api_request('sendPhoto', token, { 'chat_id' : chat_id, 'photo' : photo_url, 'caption' : caption, 'parse_mode' : parse_mode }) is not None 

def send_post(token, chat_id, post):
    photos = extract_photos(post)

    if not photos:
        send_message(token, chat_id, post['text'])
        return

    if len(photos) == 1:
        send_photo(token, chat_id, photos[0], caption=post['text']) 
        return 

    print('Too many photos')

def send_posts(token, chat_id, posts):
    for post in posts:
        send_post(token, chat_id, post)

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

def extract_id(post):
    return '{}_{}'.format(post['owner_id'], post['id'])

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


def help_command(token, msg):
    text = """
        This is help command.
    """
    send_message(token, msg['chat']['id'], text)

def get_command(token, msg, owner_id, domain, offset=0):
    global vk_token
    post = get_posts(vk_token, owner_id=owner_id, domain=domain, count=1, offset=offset)[0]
    send_post(token, msg['chat']['id'], post)

def fill_post_ids(start_date, vk_group_id, vk_group_domain):
    global vk_token, MAX_VK_POSTS_PER_REQUEST
    ids = []
    bucket_size = 1
    offset = 1

    while True:
        bucket = get_posts(vk_token, owner_id=vk_group_id, domain=vk_group_domain, count=bucket_size, offset=offset) 
        if bucket is None:
            break

        bucket_ids = list(map(extract_id, bucket))

        if datetime.fromtimestamp(bucket[-1]['date']) <= start_date:
            bad_idx = next(filter(lambda x: datetime.fromtimestamp(x[1]['date']) <= start_date, enumerate(bucket)))[0]
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


def transmit_posts(token, start_date, vk_group_id, vk_group_domain, tg_mirror_id):
    global vk_token, MAX_VK_POSTS_PER_REQUEST, start_transmitting_date
    ids = fill_post_ids(start_date, vk_group_id, vk_group_domain)

    for i in range(0, len(ids), MAX_VK_POSTS_PER_REQUEST):  
        j = min(i + MAX_VK_POSTS_PER_REQUEST, len(ids)) 
        posts = get_posts_by_ids(vk_token, ids) 

        for post in posts:
            send_post(token, tg_mirror_id, post)
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

MAX_VK_POSTS_PER_REQUEST = 100
vk_token = os.getenv('VK_TOKEN')
tg_token = os.getenv('TG_TOKEN')
smpm_id = '171296758'
smpm_domain = 'publicepsilon777'
mirror_id = '-1001642319883'
db_path = 'db.json'
start_transmitting_date = datetime(year=2022, month=9, day=1, hour=0, minute=0, second=0)


if vk_token is None:
    print('Missgin vk token')
    exit(0)

if tg_token is None:
    print('Missgin tg token')
    exit(0)

commands = { 'help' : help_command, 'get' : get_command }
offset = None 


try:
    load_from_db();

    while True:
        transmit_posts(tg_token, start_transmitting_date, smpm_id, smpm_domain, mirror_id)
        updates = get_tg_updates(tg_token, offset)
        if not updates: 
            continue

        offset = updates[-1]['update_id'] + 1

        for update in updates: 
            print('Got update')
            print(update)
            if 'message' in update and 'text' in update['message']: 
                msg = update['message']
                text = msg['text'].strip()
                if not is_command(text):
                   continue 
                
                command_name, args = parse_command(text)
                if command_name not in commands:
                    continue

                try:
                    commands[command_name](tg_token, msg, *args)
                except Exception as e:
                    print(f'Command "{command_name}" failed, args={args}')
                    print(e)
except KeyboardInterrupt:
    print("")
    pass

# TODO: support multiple photos, gifs, video
