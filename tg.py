import requests
import json
import time

from urllib.parse import quote as encode_url


def send_tg_api_request_impl(name, token, args, data):
    req_url = 'https://api.telegram.org/bot' + token + '/' + name + '?'
    for arg_name, val in args.items():
        if val:
            req_url += '{}={}&'.format(arg_name, encode_url(str(val).replace("|", "\\|")))

    req_url = req_url[:-1]
    try:
        if data is None:
            resp = requests.get(req_url)
        else:
            resp = requests.post(req_url, files=data)
    except Exception:
        return None

    return resp


def send_tg_api_request(name, token, args, data=None):
    while True:
        resp = send_tg_api_request_impl(name, token, args, data)

        if resp is None:
            return None

        if resp.status_code == 200:
            return json.loads(resp.text)['result']

        if resp.status_code == 429:
            print("Too many requests to tg api. Retrying...")
            time.sleep(0.4)
        else:
            print(f"Bad request to tg api. Response code {resp.status_code}")
            print(f"Response text: {resp.text}")
            break
    return None


def get_tg_updates(token,
                   offset=None, limit=100, timeout=1, allowed_updates=None):
    return send_tg_api_request('getUpdates', token, {
        'offset': offset,
        'limit': limit,
        'timeout': timeout,
        'allowed_updates': allowed_updates
    })


def send_message(token, chat_id, text, parse_mode=None, reply_to=None, disable_preview=True):
    return send_tg_api_request('sendMessage', token, {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': parse_mode,
        'reply_to_message_id': reply_to,
        'disable_web_page_preview': disable_preview
    })


def send_photo(token, chat_id, photo_url, caption=None, parse_mode=None, reply_to=None):
    photo_obj = requests.get(photo_url).content
    return send_tg_api_request('sendPhoto', token, {
        'chat_id': chat_id,
        'caption': caption,
        'parse_mode': parse_mode,
        'reply_to_message_id': reply_to
    }, data={"photo": photo_obj})


def send_animation(token,
                   chat_id, animation_url, caption=None, parse_mode=None, reply_to=None):
    return send_tg_api_request('sendAnimation', token, {
        'chat_id': chat_id,
        'animation': animation_url,
        'caption': caption,
        'parse_mode': parse_mode,
        'reply_to_message_id': reply_to
    })


def send_media_group(token, chat_id, media, reply_to=None):
    return send_tg_api_request('sendMediaGroup', token, {
        'chat_id': chat_id,
        'media': json.dumps(media),
        'reply_to_message_id': reply_to
    }) is not None


def remove_nans(d):
    return {k: v for k, v, in d.items() if v is not None}


def create_input_media_photo(photo_url, caption=None, parse_mode=None):
    return remove_nans({'type': 'photo', 'media': photo_url,
                        'caption': caption, 'parse_mode': parse_mode})


def send_multiphoto(token, chat_id, photos, caption=None, parse_mode=None):
    for i, url in enumerate(photos):
        if i == 0:
            photos[i] = create_input_media_photo(url, caption, parse_mode)
        else:
            photos[i] = create_input_media_photo(url)
    return send_media_group(token, chat_id, photos)
