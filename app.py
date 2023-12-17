# -*- coding: utf-8 -*-

#載入LineBot所需要的套件
from flask import Flask, request, abort

from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import *
import re
import random
import urllib.parse

# 計算距離所需要的套件
import pandas as pd
import requests
from bs4 import BeautifulSoup
from math import radians, cos, sin, asin, sqrt 
import heapq

#mongodb
from pymongo import MongoClient

app = Flask(__name__)

# 必須放上自己的Channel Access Token
line_bot_api = LineBotApi('xxxxxxxxxx')
# 必須放上自己的Channel Secret
handler = WebhookHandler('xxxxxxxxxx')
# 這裏是推給自己 message 告訴自己連接成功，因此第一個參數要放自己的 User ID
line_bot_api.push_message('xxxxxxxxxx',TextSendMessage(text='連接成功'))


# ----連接資料庫 traveling----

client = MongoClient('mongodb+srv://xxxxxxxxxx')

def get_database():
   # Provide the mongodb atlas url to connect python to mongodb using pymongo
   CONNECTION_STRING = "mongodb+srv://xxxxxxxxxx"
   # Create a connection using MongoClient.
   client = MongoClient(CONNECTION_STRING)
   # Create the database
   return client['traveling']

db = client.get_database()
placeinfo = db["placesinfo"]
users = db["users"]

#  ----定義計算距離的函式----

def count_dist(lon_1, lat_1, lon_2, lat_2):
# 將十進位制度數轉化為弧度 
    lon1, lat1, lon2, lat2 = map(radians, [lon_1, lat_1, lon_2, lat_2]) 
    # haversine公式 
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2 
    c = 2 * asin(sqrt(a)) 
    r = 6371 # 地球平均半徑，單位為公里 
    return round(c * r,1)

city_list = ['新北市','台北市','桃園市','新竹市','新竹縣','宜蘭縣','苗栗縣','台中市','彰化縣','雲林縣','嘉義縣','嘉義市','台南市','高雄市','屏東縣','花蓮縣','台東縣']

# 監聽所有來自 /callback 的 Post Request
@app.route("/callback", methods=['POST'])

def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']
 
    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

##### 機器人腳本都在這裏，依序處理： LocationMessage -> TexMessage -> PostBackEvent #####

# -----------處理地點訊息-----------

@handler.add(MessageEvent, message=LocationMessage)

def handle_message_2(event):
    if event.message.type =='location':
        user_address = event.message.address
        user_lat = event.message.latitude
        user_lon = event.message.longitude
        user_id  = event.source.user_id

        # ----取得所在地點的經緯度----
        req = requests.get(f"https://maps.googleapis.com/maps/api/geocode/json?address={user_address}&key=xxxxxxxxx&region=TW&language=zh-TW")
        res = req.json()
        user_city = res['results'][0]['address_components'][4]['long_name']

        # ----取得該user_id在users db中的message----
        search_target = users.find_one({'user-id':user_id},{'message':1, '_id':0})['message']
        if search_target == '美食':
            search_type = 'food'
        if search_target == '咖啡廳':
            search_type = 'cafe'
        if search_target == '景點':
            search_type = 'tourist_attraction'

        # ----抓出資料庫中位於同一縣市地點的id、經緯度，並存放進去字典中----
        candidate_infos = placeinfo.find({'city':user_city,'type':search_type},{'id':1,'lat':1,'lon':1,'_id':0})
        dis_dic = {}
        for info in candidate_infos:
            lat = info['lat'] #lat
            lon = info['lon'] #lon
            dis_dic[info['id']] = count_dist(float(user_lon),float(user_lat), float(lon), float(lat))

        print(dis_dic)

        urls, titles, images, addresses, google_map_urls, websites, rates, places, kws = [[] for x in range(9)]
        ids = heapq.nsmallest(3, dis_dic, key = dis_dic.get)
        for id in ids:
            detail_dic = placeinfo.find_one({'id':id},{'_id':0})
            urls.append(detail_dic['url'])
            titles.append(detail_dic['title'].split('：',1)[1])
            images.append(detail_dic['main-image'])
            addresses.append(detail_dic['address'])
            google_map_urls.append(detail_dic['google-map-url'])
            websites.append(detail_dic['website'])
            rates.append(detail_dic['rate'])
            places.append(detail_dic['place'])
            kws.append(detail_dic['kw'])
        
        search_word = user_city[:2]+search_target
        search_url = f"https://travel.yam.com/find/{urllib.parse.quote(search_word)}"
        label = f"前往官網看更多{search_word}"
        flex_message = FlexSendMessage(
        alt_text='以下三個景點推薦給你',
        contents={
            
  "type": "carousel",
  "contents": [
    {
      "type": "bubble",
      "hero": {
        "type": "image",
        "size": "full",
        "aspectRatio": "20:13",
        "aspectMode": "cover",
        "url": images[0]
      },
      "body": {
        "type": "box",
        "layout": "vertical",
        "spacing": "sm",
        "contents": [
          {
            "type": "text",
            "text": places[0],
            "wrap": True,
            "weight": "bold",
            "size": "xl",
            "margin": "none"
          },
          {
            "type": "box",
            "layout": "baseline",
            "contents": [
              {
                "type": "text",
                "text": str(rates[0]),
                "wrap": True,
                "weight": "bold",
                "size": "md",
                "flex": 0
              },
              {
                "type": "text",
                "text": "／5 (Google 評分)",
                "wrap": True,
                "weight": "regular",
                "size": "xxs",
                "flex": 0
              }
            ],
            "margin": "md",
            "spacing": "none"
          },
          {
            "type": "box",
            "layout": "baseline",
            "contents": [
              {
                "type": "text",
                "text": titles[0],
                "wrap": True,
                "weight": "regular",
                "size": "sm",
                "flex": 0
              }
            ]
          },
          {
            "type": "box",
            "layout": "baseline",
            "contents": [
              {
                "type": "text",
                "text": ','.join(kws[0][2:]),
                "weight": "regular",
                "size": "xs",
                "flex": 0,
                "margin": "none",
                "style": "italic"
              }
            ],
            "margin": "md"
          },
          {
            "type": "box",
            "layout": "baseline",
            "contents": [
              {
                "type": "text",
                "text": addresses[0],
                "wrap": True,
                "weight": "regular",
                "size": "sm",
                "flex": 0,
                "color": "#808080",
                "decoration": "none",
                "action": {
                  "type": "uri",
                  "label": "action",
                  "uri": google_map_urls[0]
                }
              }
            ],
            "spacing": "md",
            "margin": "md"
          }
        ]
      },
      "footer": {
        "type": "box",
        "layout": "vertical",
        "spacing": "sm",
        "contents": [
          {
            "type": "button",
            "style": "primary",
            "action": {
              "type": "uri",
              "label": "完整全文",
              "uri": urls[0]
            },
            "color": "#808000"
          },
          {
            "type": "button",
            "action": {
              "type": "uri",
              "label": "Google Maps",
              "uri": google_map_urls[0]
            }
          }
        ]
      }
    },
    # end of first article
    {
      "type": "bubble",
      "hero": {
        "type": "image",
        "size": "full",
        "aspectRatio": "20:13",
        "aspectMode": "cover",
        "url": images[1]
      },
      "body": {
        "type": "box",
        "layout": "vertical",
        "spacing": "sm",
        "contents": [
          {
            "type": "text",
            "text": places[1],
            "wrap": True,
            "weight": "bold",
            "size": "xl",
            "margin": "none"
          },
          {
            "type": "box",
            "layout": "baseline",
            "contents": [
              {
                "type": "text",
                "text": str(rates[1]),
                "wrap": True,
                "weight": "bold",
                "size": "md",
                "flex": 0
              },
              {
                "type": "text",
                "text": "／5 (Google 評分)",
                "wrap": True,
                "weight": "regular",
                "size": "xxs",
                "flex": 0
              }
            ],
            "margin": "md",
            "spacing": "none"
          },
          {
            "type": "box",
            "layout": "baseline",
            "contents": [
              {
                "type": "text",
                "text": titles[1],
                "wrap": True,
                "weight": "regular",
                "size": "sm",
                "flex": 0
              }
            ]
          },
          {
            "type": "box",
            "layout": "baseline",
            "contents": [
              {
                "type": "text",
                "text": ','.join(kws[1][2:]),
                "weight": "regular",
                "size": "xs",
                "flex": 0,
                "margin": "none",
                "style": "italic"
              }
            ],
            "margin": "md"
          },
          {
            "type": "box",
            "layout": "baseline",
            "contents": [
              {
                "type": "text",
                "text": addresses[1],
                "wrap": True,
                "weight": "regular",
                "size": "sm",
                "flex": 0,
                "color": "#808080",
                "decoration": "none",
                "action": {
                  "type": "uri",
                  "label": "action",
                  "uri": google_map_urls[1]
                }
              }
            ],
            "spacing": "md",
            "margin": "md"
          }
        ]
      },
      "footer": {
        "type": "box",
        "layout": "vertical",
        "spacing": "sm",
        "contents": [
          {
            "type": "button",
            "style": "primary",
            "action": {
              "type": "uri",
              "label": "完整全文",
              "uri": urls[1]
            },
            "color": "#808000"
          },
          {
            "type": "button",
            "action": {
              "type": "uri",
              "label": "Google Maps",
              "uri": google_map_urls[1]
            }
          }
        ]
      }
    },
    # end of second article
    {
      "type": "bubble",
      "hero": {
        "type": "image",
        "size": "full",
        "aspectRatio": "20:13",
        "aspectMode": "cover",
        "url": images[2]
      },
      "body": {
        "type": "box",
        "layout": "vertical",
        "spacing": "sm",
        "contents": [
          {
            "type": "text",
            "text": places[2],
            "wrap": True,
            "weight": "bold",
            "size": "xl",
            "margin": "none"
          },
          {
            "type": "box",
            "layout": "baseline",
            "contents": [
              {
                "type": "text",
                "text": str(rates[2]),
                "wrap": True,
                "weight": "bold",
                "size": "md",
                "flex": 0
              },
              {
                "type": "text",
                "text": "／5 (Google 評分)",
                "wrap": True,
                "weight": "regular",
                "size": "xxs",
                "flex": 0
              }
            ],
            "margin": "md",
            "spacing": "none"
          },
          {
            "type": "box",
            "layout": "baseline",
            "contents": [
              {
                "type": "text",
                "text": titles[2],
                "wrap": True,
                "weight": "regular",
                "size": "sm",
                "flex": 0
              }
            ]
          },
          {
            "type": "box",
            "layout": "baseline",
            "contents": [
              {
                "type": "text",
                "text": ','.join(kws[2][2:]),
                "weight": "regular",
                "size": "xs",
                "flex": 0,
                "margin": "none",
                "style": "italic"
              }
            ],
            "margin": "md"
          },
          {
            "type": "box",
            "layout": "baseline",
            "contents": [
              {
                "type": "text",
                "text": addresses[2],
                "wrap": True,
                "weight": "regular",
                "size": "sm",
                "flex": 0,
                "color": "#808080",
                "decoration": "none",
                "action": {
                  "type": "uri",
                  "label": "action",
                  "uri": google_map_urls[2]
                }
              }
            ],
            "spacing": "md",
            "margin": "md"
          }
        ]
      },
      "footer": {
        "type": "box",
        "layout": "vertical",
        "spacing": "sm",
        "contents": [
          {
            "type": "button",
            "style": "primary",
            "action": {
              "type": "uri",
              "label": "完整全文",
              "uri": urls[2]
            },
            "color": "#808000"
          },
          {
            "type": "button",
            "action": {
              "type": "uri",
              "label": "Google Maps",
              "uri": google_map_urls[2]
            }
          }
        ]
      }
    },
    # end of third article

    {
      "type": "bubble",
      "body": {
        "type": "box",
        "layout": "vertical",
        "spacing": "sm",
        "contents": [
          {
            "type": "button",
            "flex": 1,
            "gravity": "center",
            "action": {
              "type": "uri",
              "label": label,
              "uri": search_url
            }
          }
        ]
      }
    }
  ]
}
               ) #json貼在這裡

        line_bot_api.reply_message(event.reply_token, flex_message)


# -----------處理文字訊息-----------
@handler.add(MessageEvent, message=TextMessage)

# 紀錄user資料
def handle_message(event):
    message = event.message.text

    users.update_one(
        {'user-id':event.source.user_id},
        {'$set':
        {'user-id':event.source.user_id,
        'timestamp':event.timestamp,
        'message' : message},
        },
        upsert=True
        )

    # 找驚喜
    if re.match('找驚喜',message):
        buttons_template_message = TemplateSendMessage(
        alt_text='給你驚喜！',
        template=ButtonsTemplate(
            title='想找哪個地區呢？',
            text='暫不支援離島地區',
            actions=[
                MessageAction(
                    label='北部',
                    text='北部'
                ),
                MessageAction(
                    label='中部',
                    text='中部'
                ),
                MessageAction(
                    label='南部',
                    text='南部'
                ),
                MessageAction(
                    label='東部',
                    text='東部'
                )
            ]
        )
    )
        line_bot_api.reply_message(event.reply_token, buttons_template_message)

    # 選擇縣市
    elif re.match('北部',message):
        flex_message = TextSendMessage(text='你在北部的哪個縣市呢？',
                               quick_reply=QuickReply(items=[
                                   QuickReplyButton(action=PostbackTemplateAction(label="台北市", text="台北市", data='B&台北市')),
                                   QuickReplyButton(action=PostbackTemplateAction(label="新北市", text="新北市", data='B&新北市')),
                                   QuickReplyButton(action=PostbackTemplateAction(label="基隆市", text="基隆市", data='B&基隆市')),
                                   QuickReplyButton(action=PostbackTemplateAction(label="桃園市", text="桃園市", data='B&桃園市')),
                                   QuickReplyButton(action=PostbackTemplateAction(label="新竹市", text="新竹市", data='B&新竹市')),
                                   QuickReplyButton(action=PostbackTemplateAction(label="新竹縣", text="新竹縣", data='B&新竹縣')),
                                   QuickReplyButton(action=PostbackTemplateAction(label="宜蘭縣", text="宜蘭縣", data='B&宜蘭縣'))
                               ]))
        line_bot_api.reply_message(event.reply_token, flex_message)

    elif re.match('中部',message):
        flex_message = TextSendMessage(text='你在中部的哪個縣市呢？',
                               quick_reply=QuickReply(items=[
                                   QuickReplyButton(action=PostbackTemplateAction(label="苗栗縣", text="苗栗縣", data='B&苗栗縣')),
                                   QuickReplyButton(action=PostbackTemplateAction(label="台中市", text="台中市", data='B&台中市')),
                                   QuickReplyButton(action=PostbackTemplateAction(label="彰化縣", text="彰化縣", data='B&彰化縣')),
                                   QuickReplyButton(action=PostbackTemplateAction(label="南投縣", text="南投縣", data='B&南投縣')),
                                   QuickReplyButton(action=PostbackTemplateAction(label="雲林縣", text="雲林縣", data='B&雲林縣'))
                               ]))
        line_bot_api.reply_message(event.reply_token, flex_message)

    elif re.match('南部',message):
        flex_message = TextSendMessage(text='你在南部的哪個縣市呢？',
                               quick_reply=QuickReply(items=[
                                   QuickReplyButton(action=PostbackTemplateAction(label="高雄市", text="高雄市", data='B&高雄市')),
                                   QuickReplyButton(action=PostbackTemplateAction(label="台南市", text="台南市", data='B&台南市')),
                                   QuickReplyButton(action=PostbackTemplateAction(label="嘉義市", text="嘉義市", data='B&嘉義市')),
                                   QuickReplyButton(action=PostbackTemplateAction(label="嘉義縣", text="嘉義縣", data='B&嘉義縣')),
                                   QuickReplyButton(action=PostbackTemplateAction(label="屏東縣", text="屏東縣", data='B&屏東縣'))
                               ]))
        line_bot_api.reply_message(event.reply_token, flex_message)

    elif re.match('東部',message):
        flex_message = TextSendMessage(text='你在東部的哪個縣市呢？',
                               quick_reply=QuickReply(items=[
                                   QuickReplyButton(action=PostbackTemplateAction(label="花蓮縣", text="花蓮縣", data='B&花蓮縣')),
                                   QuickReplyButton(action=PostbackTemplateAction(label="台東縣", text="台東縣", data='B&台東縣'))
                               ]))
        line_bot_api.reply_message(event.reply_token, flex_message)

     # 找附近
    elif re.match('找附近',message):
        buttons_template_message = TemplateSendMessage(
        alt_text='請至手機上查看訊息',
        template=ButtonsTemplate(
            title='想找附近的哪種地點？',
            text='目前提供三種地點類型',
            actions=[
                PostbackTemplateAction(
                    label='美食',
                    text='美食',
                    data='A&美食'
                ),
                PostbackTemplateAction(
                    label='咖啡廳',
                    text='咖啡廳',
                    data='A&咖啡廳'
                ),
                PostbackTemplateAction(
                    label='景點',
                    text='景點',
                    data='A&景點'
                )
            ]
        )
    )
        line_bot_api.reply_message(event.reply_token, buttons_template_message)


    # 關鍵字搜尋
    elif re.match('找',message): 
        search = message.replace("找","")
        #detail_dic = placeinfo.find({'$or':[{'kw':{'$regex':search}},{'title':{'$regex':search}}]},{'id':1,'_id':0})
        search_word = search.encode("utf-8")
        search_url = f"https://travel.yam.com/find/{urllib.parse.quote(search_word)}"
        confirm_message = TemplateSendMessage(
        alt_text='點擊連結前往搜尋結果',
        template=ButtonsTemplate(
            title=f"{search}搜尋結果出爐！",
            text=f"點擊按鈕看{search}有哪些好景點",
            actions=[
                    URIAction(
                        label='馬上前往',
                        uri=search_url)
                ]))
        
        line_bot_api.reply_message(event.reply_token, confirm_message)


    else:
        pass

# -----------處理回傳值訊息-----------

@handler.add(PostbackEvent)

def handle_postback(event):
    if isinstance(event,PostbackEvent):
        if event.postback.data[0:1] == 'A':
            tutorial = '按左下方「+」，選擇位置資訊，將你的位置分享給我！'
            line_bot_api.reply_message(event.reply_token,TextSendMessage(tutorial))
        if event.postback.data[0:1] == 'B':
            city = event.postback.data[2:]
            buttons_template_message = TemplateSendMessage(
            alt_text='請至手機上查看訊息',
            template=ButtonsTemplate(
                title=f'想找{city}的哪種地點？',
                text='目前提供以下三種地點類型！',
                actions=[
                    PostbackTemplateAction(
                        label='美食',
                        text='美食',
                        data='C&美食&'+city
                    ),
                    PostbackTemplateAction(
                        label='咖啡廳',
                        text='咖啡廳',
                        data='C&咖啡廳&'+city
                    ),
                    PostbackTemplateAction(
                        label='景點',
                        text='景點',
                        data='C&景點&'+city
                    )
                ]
            )
        )
            line_bot_api.reply_message(event.reply_token, buttons_template_message)

        if event.postback.data[0:1] == 'C':
            type = event.postback.data.split('&')[1]
            city = event.postback.data.split('&')[2]
            if type == '美食':
                search_type = 'food'
            if type == '咖啡廳':
                search_type = 'cafe'
            if type == '景點':
                search_type = 'tourist_attraction'

            if city in city_list:
                ids_dic = placeinfo.find({'city':city,'type':search_type},{'id':1,'_id':0})
                id_lst = []
                
                for info in ids_dic:
                    id_lst.append(info['id']) 

                random_ids = random.sample(id_lst,3)
                urls, titles, images, addresses, google_map_urls, websites, rates, places, kws = [[] for x in range(9)]

                for id in random_ids:
                    detail_dic = placeinfo.find_one({'id':id},{'_id':0})
                    urls.append(detail_dic['url'])
                    titles.append(detail_dic['title'].split('：',1)[1])
                    images.append(detail_dic['main-image'])
                    addresses.append(detail_dic['address'])
                    google_map_urls.append(detail_dic['google-map-url'])
                    websites.append(detail_dic['website'])
                    rates.append(detail_dic['rate'])
                    places.append(detail_dic['place'])
                    kws.append(detail_dic['kw'])

                print(detail_dic)

                search_word = city[:2]+type
                search_url = f"https://travel.yam.com/find/{urllib.parse.quote(search_word)}"
                print(search_url)
                label = f"前往官網看更多{search_word}"
                print(label)
                flex_message = FlexSendMessage(
            alt_text='以下三個景點推薦給你',
            contents={
            
  "type": "carousel",
  "contents": [
    {
      "type": "bubble",
      "hero": {
        "type": "image",
        "size": "full",
        "aspectRatio": "20:13",
        "aspectMode": "cover",
        "url": images[0]
      },
      "body": {
        "type": "box",
        "layout": "vertical",
        "spacing": "sm",
        "contents": [
          {
            "type": "text",
            "text": places[0],
            "wrap": True,
            "weight": "bold",
            "size": "xl",
            "margin": "none"
          },
          {
            "type": "box",
            "layout": "baseline",
            "contents": [
              {
                "type": "text",
                "text": str(rates[0]),
                "wrap": True,
                "weight": "bold",
                "size": "md",
                "flex": 0
              },
              {
                "type": "text",
                "text": "／5 (Google 評分)",
                "wrap": True,
                "weight": "regular",
                "size": "xxs",
                "flex": 0
              }
            ],
            "margin": "md",
            "spacing": "none"
          },
          {
            "type": "box",
            "layout": "baseline",
            "contents": [
              {
                "type": "text",
                "text": titles[0],
                "wrap": True,
                "weight": "regular",
                "size": "sm",
                "flex": 0
              }
            ]
          },
          {
            "type": "box",
            "layout": "baseline",
            "contents": [
              {
                "type": "text",
                "text": ','.join(kws[0][2:]),
                "weight": "regular",
                "size": "xs",
                "flex": 0,
                "margin": "none",
                "style": "italic"
              }
            ],
            "margin": "md"
          },
          {
            "type": "box",
            "layout": "baseline",
            "contents": [
              {
                "type": "text",
                "text": addresses[0],
                "wrap": True,
                "weight": "regular",
                "size": "sm",
                "flex": 0,
                "color": "#808080",
                "decoration": "none",
                "action": {
                  "type": "uri",
                  "label": "action",
                  "uri": google_map_urls[0]
                }
              }
            ],
            "spacing": "md",
            "margin": "md"
          }
        ]
      },
      "footer": {
        "type": "box",
        "layout": "vertical",
        "spacing": "sm",
        "contents": [
          {
            "type": "button",
            "style": "primary",
            "action": {
              "type": "uri",
              "label": "完整全文",
              "uri": urls[0]
            },
            "color": "#808000"
          },
          {
            "type": "button",
            "action": {
              "type": "uri",
              "label": "Google Maps",
              "uri": google_map_urls[0]
            }
          }
        ]
      }
    },
    # end of first article
    {
      "type": "bubble",
      "hero": {
        "type": "image",
        "size": "full",
        "aspectRatio": "20:13",
        "aspectMode": "cover",
        "url": images[1]
      },
      "body": {
        "type": "box",
        "layout": "vertical",
        "spacing": "sm",
        "contents": [
          {
            "type": "text",
            "text": places[1],
            "wrap": True,
            "weight": "bold",
            "size": "xl",
            "margin": "none"
          },
          {
            "type": "box",
            "layout": "baseline",
            "contents": [
              {
                "type": "text",
                "text": str(rates[1]),
                "wrap": True,
                "weight": "bold",
                "size": "md",
                "flex": 0
              },
              {
                "type": "text",
                "text": "／5 (Google 評分)",
                "wrap": True,
                "weight": "regular",
                "size": "xxs",
                "flex": 0
              }
            ],
            "margin": "md",
            "spacing": "none"
          },
          {
            "type": "box",
            "layout": "baseline",
            "contents": [
              {
                "type": "text",
                "text": titles[1],
                "wrap": True,
                "weight": "regular",
                "size": "sm",
                "flex": 0
              }
            ]
          },
          {
            "type": "box",
            "layout": "baseline",
            "contents": [
              {
                "type": "text",
                "text": ','.join(kws[1][2:]),
                "weight": "regular",
                "size": "xs",
                "flex": 0,
                "margin": "none",
                "style": "italic"
              }
            ],
            "margin": "md"
          },
          {
            "type": "box",
            "layout": "baseline",
            "contents": [
              {
                "type": "text",
                "text": addresses[1],
                "wrap": True,
                "weight": "regular",
                "size": "sm",
                "flex": 0,
                "color": "#808080",
                "decoration": "none",
                "action": {
                  "type": "uri",
                  "label": "action",
                  "uri": google_map_urls[1]
                }
              }
            ],
            "spacing": "md",
            "margin": "md"
          }
        ]
      },
      "footer": {
        "type": "box",
        "layout": "vertical",
        "spacing": "sm",
        "contents": [
          {
            "type": "button",
            "style": "primary",
            "action": {
              "type": "uri",
              "label": "完整全文",
              "uri": urls[1]
            },
            "color": "#808000"
          },
          {
            "type": "button",
            "action": {
              "type": "uri",
              "label": "Google Maps",
              "uri": google_map_urls[1]
            }
          }
        ]
      }
    },
    # end of second article
    {
      "type": "bubble",
      "hero": {
        "type": "image",
        "size": "full",
        "aspectRatio": "20:13",
        "aspectMode": "cover",
        "url": images[2]
      },
      "body": {
        "type": "box",
        "layout": "vertical",
        "spacing": "sm",
        "contents": [
          {
            "type": "text",
            "text": places[2],
            "wrap": True,
            "weight": "bold",
            "size": "xl",
            "margin": "none"
          },
          {
            "type": "box",
            "layout": "baseline",
            "contents": [
              {
                "type": "text",
                "text": str(rates[2]),
                "wrap": True,
                "weight": "bold",
                "size": "md",
                "flex": 0
              },
              {
                "type": "text",
                "text": "／5 (Google 評分)",
                "wrap": True,
                "weight": "regular",
                "size": "xxs",
                "flex": 0
              }
            ],
            "margin": "md",
            "spacing": "none"
          },
          {
            "type": "box",
            "layout": "baseline",
            "contents": [
              {
                "type": "text",
                "text": titles[2],
                "wrap": True,
                "weight": "regular",
                "size": "sm",
                "flex": 0
              }
            ]
          },
          {
            "type": "box",
            "layout": "baseline",
            "contents": [
              {
                "type": "text",
                "text": ','.join(kws[2][2:]),
                "weight": "regular",
                "size": "xs",
                "flex": 0,
                "margin": "none",
                "style": "italic"
              }
            ],
            "margin": "md"
          },
          {
            "type": "box",
            "layout": "baseline",
            "contents": [
              {
                "type": "text",
                "text": addresses[2],
                "wrap": True,
                "weight": "regular",
                "size": "sm",
                "flex": 0,
                "color": "#808080",
                "decoration": "none",
                "action": {
                  "type": "uri",
                  "label": "action",
                  "uri": google_map_urls[2]
                }
              }
            ],
            "spacing": "md",
            "margin": "md"
          }
        ]
      },
      "footer": {
        "type": "box",
        "layout": "vertical",
        "spacing": "sm",
        "contents": [
          {
            "type": "button",
            "style": "primary",
            "action": {
              "type": "uri",
              "label": "完整全文",
              "uri": urls[2]
            },
            "color": "#808000"
          },
          {
            "type": "button",
            "action": {
              "type": "uri",
              "label": "Google Maps",
              "uri": google_map_urls[2]
            }
          }
        ]
      }
    },
    # end of third article

    {
      "type": "bubble",
      "body": {
        "type": "box",
        "layout": "vertical",
        "spacing": "sm",
        "contents": [
          {
            "type": "button",
            "flex": 1,
            "gravity": "center",
            "action": {
              "type": "uri",
              "label": label,
              "uri": search_url
            }
          }
        ]
      }
    }
  ]
}
               ) #json貼在這裡
        
                line_bot_api.reply_message(event.reply_token, flex_message)


#主程式
import os
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)