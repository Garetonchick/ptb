import requests
from urllib.parse import quote as encode_url
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

    if resp.status_code != 200:
        return None
    return json.loads(resp.text)['response'] 

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
    resp = send_vk_api_request('wall.get', {'access_token' : token, 'owner_id' : '-' + owner_id, 'domain' : domain, 'offset' : offset, 'count' : count, 'filter' : flt})
    return resp['items'] if resp else [] 

def get_tg_updates(token, offset = None, limit = 100, timeout = 1, allowed_updates=None):
    args = { }
    if offset:
        args['offset'] = offset
    if allowed_updates:
        args['allowed_updates'] = allowed_updates

    return send_tg_api_request('getUpdates', token, { 'offset' : offset, 'limit' : limit, 'timeout' : timeout, 'allowed_updates' : allowed_updates }) 

def send_message(token, chat_id, text, parse_mode=None):
    text = encode_url(text)
    return send_tg_api_request('sendMessage', token, { 'chat_id' : chat_id, 'text' : text, 'parse_mode' : parse_mode }) is not None 

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
    send_message(token, msg['chat']['id'], post['text'])

vk_token = os.getenv('VK_TOKEN')
tg_token = os.getenv('TG_TOKEN')

if vk_token is None:
    print('Missgin vk token')
    exit(0)

if tg_token is None:
    print('Missgin tg token')
    exit(0)

commands = { 'help' : help_command, 'get' : get_command  }
offset = None 

while True:
    updates = get_tg_updates(tg_token, offset)
    if not updates: 
        continue

    offset = updates[-1]['update_id'] + 1

    for update in updates: 
        print('Got update')
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

#print(get_posts(vk_token, owner_id='214737987', domain='phystech.confessions', count=1))

