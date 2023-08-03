import requests
from datetime import datetime
import json
import time

from urllib.parse import quote as encode_url

MAX_VK_POSTS_PER_REQUEST = 100 

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

def get_posts(token, owner_id='1', domain='apiclub', offset=0, count=1, flt='all'): 
    resp = send_vk_api_request('wall.get', {'access_token' : token, 'owner_id' : '-' + owner_id, 'domain' : domain, 'offset' : offset, 'count' : count, 'filter' : flt})
    return resp['items'] if resp else [] 

def extract_id(post):
    return '{}_{}'.format(post['owner_id'], post['id'])

def fill_post_ids(vk_token, start_date, vk_group_id, vk_group_domain):
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
