# https://github.com/line/line-bot-sdk-python
from google.cloud import datastore
from flask import Flask, request, abort, redirect
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, StickerMessage
import os
import re
import config

app = Flask(__name__)

url_github = "https://github.com/dr666m1/project_shiki_cast_bot"
line_bot_api = LineBotApi(config.token)
handler = WebhookHandler(config.secret)
client = datastore.Client()

@app.route("/")
def github():
    return redirect(url_github)

@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']
    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body) # output log to stdout
    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)
    return 'OK'

def send_message(event, msg=None):
    if msg is None:
        msg = '何かお困りですか？\n使い方は説明書をご確認ください。\n\n{}\n\n※環境によってはView all of README.mdを押さないと全文表示されません。'.format(url_github)
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=msg)
    )

upsert_message = [
    "【{}】さん推しなんですね！\n出演が決まったら連絡します。",
    "【{}】さん推しやめるんですね？\n気が変わったら教えてください。",
]

def upsert_fan(event, key_user, cast):
    entity_user = client.get(key_user)
    if entity_user is None:
        entity_user = datastore.Entity(key=key_user)
        favorites = [cast]
        message = 0
    else:
        favorites_prev = entity_user["favorites"]
        if cast in favorites_prev:
            favorites = [x for x in favorites_prev if x != cast]
            message = 1
        else:
            favorites = favorites_prev + [cast]
            message = 0
    entity_user.update({
        "favorites": favorites
    })
    client.put(entity_user)
    send_message(event, upsert_message[message].format(cast))

@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    text = re.sub("[ 　]", "", event.message.text) # delete space
    user_id = event.source.user_id
    if 2 <= len(event.message.text.split("\n")):
        send_message(event)
    else:
        key_cast = client.key("Cast", text)
        entity_cast = client.get(key_cast)
        if entity_cast is None:
            send_message(event, "【{}】さんは知らないです...\nごめんなさい！".format(text))
        else:
            key_user = client.key("Fan", user_id)
            upsert_fan(event, key_user, key_cast.name)

@handler.add(MessageEvent, message=StickerMessage)
def handle_sticker_message(event):
    key_user = client.key("Fan", event.source.user_id)
    entity_user = client.get(key_user)
    try:
        favorites = entity_user["favorites"]
    except TypeError as e:
        favorites = []
    if favorites == []:
        send_message(event, "よかったら好きなキャストさんを教えてください。")
    else:
        reply = "\n".join([f + "さん" for f in favorites]) + "\n推しなんですね！"
        send_message(event, reply)

if __name__ == "__main__":
    app.run(debug=True,host='0.0.0.0',port=int(os.environ.get('PORT', 8080)))
