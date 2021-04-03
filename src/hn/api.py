import json
import os

import requests

from typing import List
from dataclasses import dataclass

from pango import html_to_pango

session = requests.Session()

@dataclass(frozen=True)
class Comment:
    user: str
    markup: str
    kids: List[int]
    dead: bool
    deleted: bool

@dataclass(frozen=True)
class Story:
    story_id: int
    title: str
    url: str
    url_domain: str
    kids: List[int]
    comment_count: int
    score: int

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

def get_story(_id) -> Story:
    raw_data = get_id(_id)
    comment_count = raw_data.get('descendants', 0)
    kids = raw_data.get('kids', [])
    score = raw_data['score']
    title = raw_data['title']
    if raw_data.get('url'):
        url = raw_data['url']
        url_domain = raw_data['url'].split('/')[2]
    else:
        url = 'self'
        url_domain = 'self'

    return Story(story_id=_id, title=title, url=url, url_domain=url_domain,
                 kids=kids, comment_count=comment_count, score=score)

def get_comment(_id) -> Comment:
    raw_data = get_id(_id)
    deleted = False
    dead = False
    markup = ''
    user = ''
    if 'text' not in raw_data:
        deleted = True
        markup = 'deleted'
        user = 'deleted'
    else:
        markup = html_to_pango(raw_data['text'])
        user = raw_data['by']

    dead = raw_data.get('dead', False)
    kids = raw_data.get('kids', [])

    return Comment(user=user, markup=markup, kids=kids,
                   dead=dead, deleted=deleted)
