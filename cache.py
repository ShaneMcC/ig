import hashlib
import json
import sqlite3
from enum import Enum, auto
from typing import List, Dict

import yaml
from bs4 import BeautifulSoup
from requests import Session


class MediaType(Enum):
    IMAGE = auto()
    SIDECAR = auto()
    VIDEO = auto()


class MediaObject:
    username: str
    shortcode: str
    type: str
    caption: str
    thumbnail: str
    medias: List[str]
    timestamp: int

    def __init__(self, username: str, shortcode: str, type: MediaType, caption: str, thumbnail: str, timestamp: int):
        self.username = username
        self.shortcode = shortcode
        self.type = type
        self.caption = caption
        self.thumbnail = thumbnail
        self.medias = []
        self.timestamp = timestamp

    def addmedia(self, media):
        self.medias.append(media)

    def __repr__(self):
        return "<MediaObject shortcode:%s type:%s>" % (self.shortcode, self.type)

    def __str__(self):
        return "type:%s - shortcode:%s" % (self.type, self.shortcode)


class Timeline:
    username: str
    end_cursor: str
    medias: List[MediaObject]
    count = 0
    session: Session
    rhx_gis: str
    data: Dict
    userid: str

    def __init__(self, username: str, count: int):
        self.username = username
        self.count = count
        self.medias = []
        self.session = Session()
        self.rhx_gis: str = None
        self.userid: str = None
        self.data = None

    def get_timelime(self):
        currentcount = 0
        self.data = self.get_shareddata(self.username)
        while currentcount < self.count:
            if self.data is not None:
                if 'entry_data' in self.data:
                    edges = \
                        self.data['entry_data']['ProfilePage'][0]['graphql']['user']['edge_owner_to_timeline_media'][
                            'edges']
                else:
                    edges = self.data['data']['user']['edge_owner_to_timeline_media']['edges']
                for edge in edges:
                    node = edge['node']
                    if node['__typename'] == 'GraphImage':
                        self.addmedia(self.get_image(self.username, node['shortcode']))
                    elif node['__typename'] == 'GraphSidecar':
                        self.addmedia(self.get_sidecars(self.username, node['shortcode']))
                    elif node['__typename'] == 'GraphVideo':
                        self.addmedia(self.get_video(self.username, node['shortcode']))
                    else:
                        raise TypeError('Unknown edge type.')
                currentcount = len(self.medias)
                if currentcount < self.count:
                    self.data = self.get_more(
                        self.data['entry_data']['ProfilePage'][0]['graphql']['user']['edge_owner_to_timeline_media'][
                            'page_info']['end_cursor'])
            else:
                raise EnvironmentError('Unable to get data.')

    def addmedia(self, media):
        self.medias.append(media)

    def get_video(self, username: str, shortcode: str) -> MediaObject:
        data = self.get_shareddata(shortcode, 'p')
        caption = ''
        if len(data['entry_data']['PostPage'][0]['graphql']['shortcode_media']['edge_media_to_caption'][
                'edges']) > 0:
            caption = data['entry_data']['PostPage'][0]['graphql']['shortcode_media']['edge_media_to_caption'][
                'edges'][0]['node']['text']
        media = MediaObject(username, shortcode,
                            MediaType.VIDEO,
                            caption,
                            data['entry_data']['PostPage'][0]['graphql']['shortcode_media']['display_url'],
                            data['entry_data']['PostPage'][0]['graphql']['shortcode_media']['taken_at_timestamp'])
        media.addmedia(data['entry_data']['PostPage'][0]['graphql']['shortcode_media']['video_url'])
        return media

    def get_sidecars(self, username: str, shortcode: str) -> MediaObject:
        data = self.get_shareddata(shortcode, 'p')
        caption = ''
        if len(data['entry_data']['PostPage'][0]['graphql']['shortcode_media']['edge_media_to_caption'][
                                'edges']) > 0:
            caption = data['entry_data']['PostPage'][0]['graphql']['shortcode_media']['edge_media_to_caption'][
                                'edges'][0]['node']['text']
        media = MediaObject(username, shortcode,
                            MediaType.SIDECAR,
                            caption,
                            data['entry_data']['PostPage'][0]['graphql']['shortcode_media']['display_url'],
                            data['entry_data']['PostPage'][0]['graphql']['shortcode_media']['taken_at_timestamp'])
        for edge in data['entry_data']['PostPage'][0]['graphql']['shortcode_media']['edge_sidecar_to_children'][
            'edges']:
            media.addmedia(edge['node']['display_url'])
        return media

    def get_image(self, username: str, shortcode: str) -> MediaObject:
        data = self.get_shareddata(shortcode, 'p')
        caption = ''
        if len(data['entry_data']['PostPage'][0]['graphql']['shortcode_media']['edge_media_to_caption'][
                                'edges']) > 0:
            caption = data['entry_data']['PostPage'][0]['graphql']['shortcode_media']['edge_media_to_caption'][
                                'edges'][0]['node']['text']
        media = MediaObject(username, shortcode,
                            MediaType.IMAGE,
                            caption,
                            data['entry_data']['PostPage'][0]['graphql']['shortcode_media']['display_url'],
                            data['entry_data']['PostPage'][0]['graphql']['shortcode_media']['taken_at_timestamp'])
        media.addmedia(data['entry_data']['PostPage'][0]['graphql']['shortcode_media']['display_url'])
        return media

    def get_url(self, id: str, path: None):
        if path is None:
            return 'https://www.instagram.com/{0}'.format(id)
        else:
            return 'https://www.instagram.com/{0}/{1}'.format(path, id)

    def get_shareddata(self, id: str, path=None):
        data = None
        response = (self.session.get(self.get_url(id, path)))
        html = BeautifulSoup(response.content, 'html.parser')
        for script in html.select('script'):
            if script.text.startswith('window._sharedData'):
                data = json.loads(script.text.split('window._sharedData = ')[1][:-1])
        if data is None:
            raise ValueError('Unable to find shared data.')
        self.rhx_gis = data['rhx_gis']
        if path is None:
            self.userid = data['entry_data']['ProfilePage'][0]['graphql']['user']['id']
        return data

    def get_more(self, after: str):
        variables = json.dumps({'id': self.userid, 'first': 12, 'after': after})
        params = [('query_id', '17888483320059182'), ('variables', variables)]
        response = self.session.get('https://www.instagram.com/graphql/query/', params=params,
                                    headers={'x-instagram-gis': self.get_ig_gis(variables)})
        return json.loads(response.content)

    def get_ig_gis(self, params: str):
        return hashlib.md5((self.rhx_gis + ":" + params).encode('utf-8')).hexdigest()

    def __repr__(self):
        return "<Timeline username:%s max:%s>" % (self.username, self.count)

    def __str__(self):
        return "username:%s - max count:%s" % (self.username, self.count)


class DBA:
    path: str
    conn: sqlite3.Connection

    def __init__(self, dbpath: str):
        self.conn = None
        self.path = dbpath

    def init(self):
        self.conn = sqlite3.connect(self.path + '/database.sqlite')
        self.inittables()

    def inittables(self):
        c = self.conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (
                                id INTEGER PRIMARY KEY,
                                username TEXT UNIQUE,
                                lastpoll INTEGER
                                )''')
        c.execute('''CREATE TABLE IF NOT EXISTS medias (
                                shortcode TEXT PRIMARY KEY,
                                username TEXT,
                                thumbnailURL TEXT,
                                imageURL TEXT,
                                caption TEXT,
                                timestamp INTEGER
                            )''')
        self.conn.commit()

    def close(self):
        self.conn.close()

    def addusers(self, users: dict):
        for user in users:
            self.conn.cursor().execute('''insert or replace into users(username) values (?)''', (user,))
            self.conn.commit()

    def pruneusers(self, users: dict):
        prunes = set(users) - set(x[0] for x in self.conn.cursor().execute('''select username from users''').fetchall())
        if len(prunes) > 0:
            self.conn.cursor().executemany('''delete from users where username=?''', [prunes])
            self.conn.cursor().execute('''delete from medias where username not in (select username from users)''')
            self.conn.commit()

    def addmedia(self, media: MediaObject):
        for index, imageurl in enumerate(media.medias):
            print(index)
            self.conn.cursor().execute(
                '''insert or replace into medias(shortcode,username,thumbnailURL,imageURL,caption,timestamp) values (?,?,?,?,?,?)''',
                (media.shortcode + str(index), media.username, media.thumbnail, imageurl, media.caption, media.timestamp))
            self.conn.commit()


def getconfig() -> Dict:
    try:
        with open('config.yml', 'r') as ymlfile:
            config = yaml.load(ymlfile)
            return config
    except FileNotFoundError:
        print('Unable to find config file.')
        raise SystemExit


cfg = getconfig()
db = DBA('.')
db.init()
db.addusers(cfg['users'])
db.pruneusers(cfg['users'])

timelines = []
for user in cfg['users']:
    timelines.append(Timeline(user, 13))

for timeline in timelines:
    timeline.get_timelime()
    for media in timeline.medias:
        db.addmedia(media)