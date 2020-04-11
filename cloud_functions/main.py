import requests
import lxml.html
import time
import random
import datetime
import re
from google.cloud import datastore
from linebot import LineBotApi
from linebot.models import TextSendMessage
import config_line

#===== common =====
base_url = "https://www.shiki.jp/cast/"

def get_html_element(url):
    html = requests.get(url).text
    root = lxml.html.fromstring(html)
    return root

def get_prod_infos():
    root = get_html_element(base_url)
    prod_names = root.xpath("//div[@class='productionList']/a/text()")
    prod_urls = ["https://www.shiki.jp" + x for x in root.xpath("//div[@class='productionList']/a/@href")]
    prod_infos = {
        "names": prod_names,
        "urls": prod_urls,
    }
    return prod_infos

def random_sleep(sec=2): # 本番は100とか
    time.sleep(random.randint(1, sec))

def upsert_entity(key, no_idx=None, **kwargs):
    """
    after this function,
    you have to run `client.put` or `client.put_multi`
    """
    if no_idx is None:
        no_idx = list(kwargs.keys())
    entity = datastore.Entity(key, exclude_from_indexes=no_idx)
    entity.update(kwargs)
    return entity

#===== check_update =====
def check_update():
    random_sleep()
    prod_infos = get_prod_infos()
    prod_names = prod_infos["names"]
    prod_urls = prod_infos["urls"]
    prod_updates = []
    n_prod = len(prod_urls)
    for i in range(n_prod):
        random_sleep()
        prod_url =prod_urls[i]
        prod_root = get_html_element(prod_url)
        prod_updates += prod_root.xpath("//span[@class='date']/text()")
    client = datastore.Client()
    def tmp(x):
        try:
            res = client.get(client.key("Prod", x))["updatedAt"]
            return res
        except TypeError as e: # in the case of new production
            return ''
    prod_updates_prev = [tmp(x) for x in prod_names]
    res = all([x != y for x, y in zip(prod_updates, prod_updates_prev)])
    if res:
        entities = [
            upsert_entity(client.key("Prod", prod_names[i]), updatedAt=prod_updates[i])
            for i in range(n_prod)
        ]
        client.put_multi(entities)
    else:
        raise Exception("some productions are not up to date")

#===== scrape =====
def parse_cast_td(td):
    html = lxml.html.tostring(td, encoding="utf-8").decode()
    casts = [re.sub(r"（.*）|<[^<]*>|[ 　]+", "", x) for x in html.split("<br>")]
    return casts

def scrape():
    random_sleep()
    yyyymmdd = datetime.datetime.now().strftime("%Y%m%d")
    prod_infos = get_prod_infos()
    n_prod = len(prod_infos["urls"])
    client = datastore.Client()
    no_idx = ["character", "prod"]
    for i in range(n_prod):
        url = prod_infos["urls"][i]
        prod = prod_infos["names"][i]
        random_sleep
        root = get_html_element(url)
        character_tds = root.xpath("//td[@class='top']")
        for td in character_tds:
            character = td.text
            casts = parse_cast_td(td.getparent()[1])
            entities = [
                upsert_entity(client.key("Cast", c), no_idx=no_idx, updatedAt=yyyymmdd, character=character, prod=prod)
                for c in casts
            ]
            client.put_multi(entities)

#===== weekly message =====
msg = "今週【{}】さんが「{}」に出演します。\n当日券で会いに行きましょう！"

def send_msg(updatedAt=datetime.datetime.now().strftime("%Y%m%d")):
    client = datastore.Client()
    line_bot_api = LineBotApi(config_line.token)
    # get all casts
    query = client.query(kind="Cast")
    query.add_filter("updatedAt", "=", updatedAt)
    casts = query.fetch()
    # get fan of the cast
    for c in casts: #casts:
        cast = c.key.name
        query = client.query(kind="Fan")
        query.add_filter("favorites", "=", cast)
        ids = [x.key.name for x in query.fetch()]
        if ids != []:
            line_bot_api.multicast(ids, TextSendMessage(text=msg.format(c.key.name, c["prod"])))
