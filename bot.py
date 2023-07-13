import requests
import json
import os

def send_vk_api_request(name, args, version='5.131'):
    req_url = 'https://api.vk.com/method/' + name + '?'
    for arg_name, val in args.items():
        req_url += '{}={}&'.format(arg_name, val)
    req_url += 'v=' + version
    try:
        resp = requests.get(req_url)
    except:
        return None
    return resp.text if resp.status_code == 200 else None

def send_tg_api_request(name, token, args):
    req_url = 'https://api.telegram.org/bot' + token + '/' + name + '?'
    for arg_name, val in args.items():
        if val:
            req_url += '{}={}&'.format(arg_name, val)

    req_url = req_url[:-1]
    try:
        resp = requests.get(req_url)
    except:
        return None

    if resp.status_code != 200:
        return None

    resp_decoded = json.loads(resp.text)
    return resp_decoded['result'] if resp_decoded['ok'] else None

def get_posts(token, owner_id='1', domain='apiclub', offset=0, count=1, flt='all'): 
    return send_vk_api_request('wall.get', {'access_token' : token, 'owner_id' : '-' + owner_id, 'domain' : domain, 'offset' : offset, 'count' : count, 'filter' : flt})

def get_tg_updates(token, offset = None, limit = 100, timeout = 1, allowed_updates=None):
    args = { }
    if offset:
        args['offset'] = offset
    if allowed_updates:
        args['allowed_updates'] = allowed_updates

    return send_tg_api_request('getUpdates', token, { 'offset' : offset, 'limit' : limit, 'timeout' : timeout, 'allowed_updates' : allowed_updates }) 

def send_message(token, chat_id, text, parse_mode=None):
    return send_tg_api_request('sendMessage', token, { 'chat_id' : chat_id, 'text' : text, 'parse_mode' : parse_mode }) is not None 

def process_update(upd):
    print(upd)

vk_token = os.getenv('VK_TOKEN')
tg_token = os.getenv('TG_TOKEN')

#print(get_posts(vk_token, owner_id='214737987', domain='phystech.confessions', count=1))

offset = None 

while True:
    updates = get_tg_updates(tg_token, offset)
    if not updates: 
        continue

    offset = updates[-1]['update_id'] + 1

    for update in updates: 
        if 'message' in update and 'text' in update['message']: 
            send_message(tg_token, update['message']['chat']['id'], update['message']['text'])

#print(get_tg_updates(tg_token))
