#_*_ encoding:utf8 _*_
from flask import (Flask, render_template, redirect, url_for, request, flash ,jsonify,session)
import redis
import json
from datetime import datetime,timedelta
import time
import Queue
import pdb

import re
import HTMLParser
import urllib,urllib2
agent = {'User-Agent':'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/34.0.1847.137 Safari/537.36 LBBROWSER'}

# pdb.set_trace()
app = Flask(__name__)
_REDIS_HOST = "54.161.160.206"
_REDIS_PORT = 7379
_FETCH_KEY = 'task:events'
_FETCH_LOCS_KEY = 'task:locs'
r = redis.Redis(host=_REDIS_HOST,port=_REDIS_PORT)
_INDEX_COUNT = 10
_COUNT=0
_LOCS_COUNT=0
@app.route('/form-results')
def form_results():
    return render_template('form-results.html')
@app.route('/getlocs')
def getLocs():
    global _LOCS_COUNT
    if r.llen(_FETCH_LOCS_KEY)>_LOCS_COUNT:
        raw = r.lrange(_FETCH_LOCS_KEY,_LOCS_COUNT,_LOCS_COUNT)
        _batch = []
        for e in raw:
            _e = json.loads(e)
            text = _e["text"]
            _e['trans'] = translate(text).strip("'")
            _e['count'] = _LOCS_COUNT
            _batch.append(json.dumps(_e))
        _LOCS_COUNT+=1
    else:
        _batch =["{}"]
    return jsonify({'ret':True,'data':_batch})

@app.route('/fetchone')
def fetchone():
    global _COUNT
    if r.llen(_FETCH_KEY)>_COUNT:
        raw = r.lrange(_FETCH_KEY,_COUNT,_COUNT)
        _COUNT+=1
    else:
        _batch =["{}"]

    return jsonify({'ret':True,'data':_batch})


@app.route('/fetch_batch_persist')
def fetch_batch_persisit():
    global _COUNT
    print(_COUNT)
    batch_num = int(request.args.get("num"))
    if batch_num<=0:
        print("less num")
        return jsonify({"ret":False,'data':None})
    batch = []
    rlen = r.llen(_FETCH_KEY)
    if rlen >=_COUNT+batch_num-1:
        batch = r.lrange(_FETCH_KEY,_COUNT,_COUNT+batch_num-1)
        _COUNT += batch_num
    elif rlen>=_COUNT:
        batch = r.lrange(_FETCH_KEY,_COUNT,rlen)
        _COUNT=rlen+1
    else:
        return jsonify({"ret":False,'data':None})
    _batch = []
    for e in batch:
        _e = json.loads(e)
        _url = "https://twitter.com/twitter/status/"+_e['id']
        _e['url'] = '<a href=\"'+_url+'\">check tweet</a>'
        text = _e["ptweet"]
        _e['trans'] = translate(text).strip("'")
        _batch.append(json.dumps(_e))
    # for i in range(batch_num):
    #     _batch.append(json.dumps({'name':'this is event'+str(i),'coords':[14+i*3,10+i*3]}))
    return jsonify({'ret':True,'data':_batch})


@app.route('/fetch_batch')
def fetch_batch():
    batch_num = int(request.args.get("num"))
    if batch_num<=0:
        print("less num")
        return jsonify({"ret":False,'data':None})
    batch = []
    for i in range(batch_num):
        raw = r.lpop(_FETCH_KEY)
        if not raw:
            continue
        batch.append(raw)
    if len(batch)<=0:
        print("less row")
        return jsonify({"ret":False,'data':None})

    return jsonify({'ret':True,'data':batch})


@app.route('/index')
def index():
    _COUNT=0
    events = []
    return render_template('index.html',events = events)

def index_show():
    global _COUNT
    events = []
    length = r.llen(_FETCH_KEY)
    if length>100:
        _COUNT=length-100

    elif length>0:
        _COUNT = length+1 if length < _INDEX_COUNT-1 else _INDEX_COUNT
    else:
        events = []
    return events

def constant_show():
    global _COUNT
    events = []
    length = r.llen(_FETCH_KEY)
    if length>100:
        _COUNT=length-100
        events = [e for e in r.lrange(_FETCH_KEY,_COUNT,_COUNT+_INDEX_COUNT-1)]
        _COUNT = _COUNT+_INDEX_COUNT

    elif length>0:
        events = [json.loads(e) for e in r.lrange(_FETCH_KEY,0,_INDEX_COUNT-1)]
        _COUNT = length+1 if length < _INDEX_COUNT-1 else _INDEX_COUNT
    else:
        events = []
    _events = []
    if len(events)<=0:
        return None
    # for _e in events:
    #     # _url = "https://twitter.com/twitter/status/"+_e['id']
    #     # _e['url'] = '<a href=\"'+_url+'\">check tweet</a>'
    #     text = _e['ptweet']
    #     # text_zh=translate(text).strip("'")
    #     # _e['trans'] = text_zh
    #     _e['trans'] = "fanyi"
    #     _events.append(_e)    
    return events
def consume_show():
    count=0
    events = []
    while count<_INDEX_COUNT:
        raw = r.lpop(_FETCH_KEY)
        count+=1
        while not raw:
            time.sleep(1)
            raw = r.lpop(_FETCH_KEY)
            count+=1
        _e = json.loads(raw)
        _url = "https://twitter.com/twitter/status/"+_e['id']
        _e['url'] = '<a href=\"'+_url+'\">check tweet</a>'
        text = raw['ptweet']
        text_zh=translate(text).strip("'")      
        _e['trans'] = text_zh
        _e['trans'] = "fanyi"
        events.append(_e)
    return events

def unescape(text):
    parser = HTMLParser.HTMLParser()
    return (parser.unescape(text))

def translate(text, fromLang="auto", toLang="zh-CN"):
    base_link = "http://translate.google.cn/m?hl=%s&sl=%s&q=%s"
    text = re.sub(r'[^A-Za-z0-9\'\":/\.&$|@%\\]',' ',text)
    r_filter = r"(bitch|pussy|dick|ass|fuck|rape|wet)"
    text = re.sub(r_filter,"*",text)
    text = urllib.quote_plus(text)
    link = base_link % (toLang, fromLang, text)
    request = urllib2.Request(link, headers=agent)
    try:
        raw_data = urllib2.urlopen(request).read()
        data = raw_data.decode("utf-8")
        expr = r'class="t0">(.*?)<'
        re_result = re.findall(expr, data)
        if (len(re_result) == 0):
            result = ""
        else:
            result = unescape(re_result[0])
        return (result)
    except Exception as e:
        print(e)
        return text
if __name__=="__main__":
    app.run(debug=True,host='0.0.0.0',port=2018)

