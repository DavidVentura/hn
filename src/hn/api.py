import json
import os

import requests

session = requests.Session()

def top_stories():
    if os.path.exists('topstories.json'):
        return json.load(open('topstories.json'))
    r = session.get('https://hacker-news.firebaseio.com/v0/topstories.json')
    with open('topstories.json','w') as fd:
        fd.write(r.text)
    return r.json()


def get_id(_id):
    if os.path.exists(f'{_id}.json'):
        return json.load(open(f'{_id}.json'))
    r = session.get(f'https://hacker-news.firebaseio.com/v0/item/{_id}.json')
    open(f'{_id}.json', 'w').write(r.text)
    data = r.json()
    return data



