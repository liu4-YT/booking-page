from flask import Flask, request, jsonify
import time, urllib.request, json, sys, os, random, datetime, hashlib, uuid
import xml.etree.ElementTree as ET

app = Flask(__name__)

# ============ 飞书配置 ============
FS_ID = 'cli_aaeacecbf47a9bc0'
FS_SK = 'UmiNOo8IHbFIb1iLwEaa8gNreIem2nVD'
BASE_ID = 'QXazbngDbamnwGsMjEbc58TGnDh'
TABLE_ID = 'tblRD66BfFKmKQQl'          # 预约表
SIGNIN_TABLE_ID = 'tblhPQLEX6UYiF9J'  # 签到记录表
TICKET_TABLE_ID = 'tblbt4JR82mCXUwU'  # 门票表
CACHE_FILE = '/home/liuyt/booking_cache.json'

# ============ 微信配置 ============
WX_APPID = 'wxbbe6957098d94a79'
WX_SECRET = '85de7feed90d1b5871cccc5006460dd6'
WX_TOKEN = 'shudashui_token_2026'   # 公众号后台填的 Token，需与后台一致

# ============ 门票使用限制（后续改这里即可） ============
TICKET_RULES = {
    'type': '全天不限时畅玩',   # 门票类型
    'expire_days': 0,          # 0=永久有效；N=领取后N天内有效
    'usable_weekdays': [],     # []任意；[5,6]仅周五周六（0=周一）
    'usable_hours': [],        # []不限；['10:00','24:00']限时段
    'signin_days_needed': 7,   # 连续签到多少天发一张
}

_token = None
_token_expire = 0
_bookings = {}
_codes = {}
_initialized = False
_last_refresh = 0
_REFRESH_INTERVAL = 30


def log(m):
    print('===BOOKING_API=== ' + m, file=sys.stderr, flush=True)


@app.after_request
def add_cors(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response


def get_token():
    global _token, _token_expire
    now = time.time()
    if _token and now < _token_expire - 60:
        return _token
    d = json.dumps({'app_id': FS_ID, 'app_secret': FS_SK}).encode()
    req = urllib.request.Request(
        'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
        data=d, headers={'Content-Type': 'application/json; charset=utf-8'}
    )
    body = json.loads(urllib.request.urlopen(req, timeout=5).read())
    _token = body['tenant_access_token']
    _token_expire = now + body.get('expire', 7200)
    return _token


def load_from_feishu(force=False):
    global _bookings, _codes, _initialized, _last_refresh
    now = time.time()
    if _initialized and not force and (now - _last_refresh) < _REFRESH_INTERVAL:
        return
    _initialized = False
    _bookings = {}
    _codes = {}
    try:
        token = get_token()
        h = {'Authorization': 'Bearer ' + token}
        api_url = 'https://open.feishu.cn/open-apis/bitable/v1/apps/' + BASE_ID + '/tables/' + TABLE_ID + '/records?page_size=100'
        page_token = None
        for _ in range(3):
            url = api_url + ('&page_token=' + page_token if page_token else '')
            data = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=4).read())
            for item in data.get('data', {}).get('items', []):
                f = item.get('fields', {})
                r = (f.get('项目') or '').strip()
                d = (f.get('日期') or '').strip()
                t = (f.get('时间') or '').strip()
                c = (f.get('手环编号') or '').strip()
                if r and d and t:
                    _bookings.setdefault(r, {}).setdefault(d, [])
                    if t not in _bookings[r][d]:
                        _bookings[r][d].append(t)
                    if c:
                        _codes.setdefault(r, {}).setdefault(d, {})
                        _codes[r][d][c] = True
            if not data.get('data', {}).get('has_more'):
                break
            page_token = data.get('data', {}).get('page_token', '') or ''
        _initialized = True
        _last_refresh = time.time()
        save_cache()
        log('loaded from feishu: ' + str(_bookings))
    except Exception as e:
        log('feishu load err: ' + str(e))
        try:
            if os.path.exists(CACHE_FILE):
                with open(CACHE_FILE) as f:
                    cached = json.loads(f.read() or '{}')
                    _bookings = cached.get('bookings', {})
                    _codes = cached.get('codes', {})
                log('fallback to file: ' + str(_bookings))
        except Exception as e2:
            log('fallback err: ' + str(e2))
        _initialized = True


def save_cache():
    try:
        with open(CACHE_FILE, 'w') as f:
            f.write(json.dumps({'bookings': _bookings, 'codes': _codes}))
    except Exception as e:
        log('save_cache err: ' + str(e))


def write_feishu(data):
    token = get_token()
    code = (data.get('code') or '').strip()
    room = (data.get('roomName') or '').strip()
    date = (data.get('date') or '').strip()
    time_val = (data.get('time') or '').strip()
    remark = (data.get('remark') or '').strip()
    body = json.dumps({'fields': {'手环编号': code, '项目': room, '日期': date, '时间': time_val, '备注': remark}}).encode('utf-8')
    url = 'https://open.feishu.cn/open-apis/bitable/v1/apps/' + BASE_ID + '/tables/' + TABLE_ID + '/records'
    req = urllib.request.Request(url, data=body, headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json; charset=utf-8'})
    return json.loads(urllib.request.urlopen(req, timeout=8).read())


# ============ 飞书通用：查询表记录 ============
def feishu_list_records(table_id, page_size=100):
    token = get_token()
    h = {'Authorization': 'Bearer ' + token}
    out = []
    page_token = None
    for _ in range(10):
        url = 'https://open.feishu.cn/open-apis/bitable/v1/apps/' + BASE_ID + '/tables/' + table_id + '/records?page_size=' + str(page_size)
        if page_token:
            url += '&page_token=' + page_token
        data = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=8).read())
        out.extend(data.get('data', {}).get('items', []))
        if not data.get('data', {}).get('has_more'):
            break
        page_token = data.get('data', {}).get('page_token', '') or ''
        if not page_token:
            break
    return out


def feishu_add_record(table_id, fields):
    token = get_token()
    body = json.dumps({'fields': fields}).encode('utf-8')
    url = 'https://open.feishu.cn/open-apis/bitable/v1/apps/' + BASE_ID + '/tables/' + table_id + '/records'
    req = urllib.request.Request(url, data=body, headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json; charset=utf-8'})
    return json.loads(urllib.request.urlopen(req, timeout=8).read())


def feishu_update_record(table_id, record_id, fields):
    token = get_token()
    body = json.dumps({'fields': fields}).encode('utf-8')
    url = 'https://open.feishu.cn/open-apis/bitable/v1/apps/' + BASE_ID + '/tables/' + table_id + '/records/' + record_id
    req = urllib.request.Request(url, data=body, headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json; charset=utf-8'}, method='PUT')
    return json.loads(urllib.request.urlopen(req, timeout=8).read())


# ============ 微信：code 换 openid ============
def wx_code2session(code):
    url = 'https://api.weixin.qq.com/sns/oauth2/access_token?appid=' + WX_APPID + '&secret=' + WX_SECRET + '&code=' + code + '&grant_type=authorization_code'
    data = json.loads(urllib.request.urlopen(url, timeout=8).read())
    return data.get('openid', '')


# ============ 签到逻辑 ============
def get_signin_info(openid):
    """返回 {today_signed: bool, streak: int, last_date: str}"""
    records = feishu_list_records(SIGNIN_TABLE_ID)
    today = datetime.date.today().strftime('%Y-%m-%d')
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    my_records = []
    for item in records:
        f = item.get('fields', {})
        if (f.get('openid') or '').strip() == openid:
            my_records.append(f)
    # 找到最近一次签到
    my_records.sort(key=lambda f: f.get('签到日期', ''), reverse=True)
    if not my_records:
        return {'today_signed': False, 'streak': 0, 'last_date': ''}
    last = my_records[0]
    last_date = (last.get('签到日期') or '').strip()
    streak = int(last.get('连续天数') or 0)
    if last_date == today:
        return {'today_signed': True, 'streak': streak, 'last_date': last_date}
    elif last_date == yesterday:
        return {'today_signed': False, 'streak': streak, 'last_date': last_date}
    else:
        return {'today_signed': False, 'streak': 0, 'last_date': last_date}


def do_signin(openid):
    info = get_signin_info(openid)
    today = datetime.date.today().strftime('%Y-%m-%d')
    if info['today_signed']:
        return {'already': True, 'streak': info['streak'], 'ticket': None}

    # 计算连续天数
    if info['last_date'] == (datetime.date.today() - datetime.timedelta(days=1)).strftime('%Y-%m-%d'):
        new_streak = info['streak'] + 1
    else:
        new_streak = 1

    # 写入签到记录
    feishu_add_record(SIGNIN_TABLE_ID, {
        'openid': openid,
        '签到日期': today,
        '连续天数': new_streak
    })

    # 判断是否发门票
    ticket = None
    if new_streak >= TICKET_RULES['signin_days_needed']:
        ticket = issue_ticket(openid)

    return {'already': False, 'streak': new_streak, 'ticket': ticket}


def issue_ticket(openid):
    """发一张门票，返回核销码。同一 openid 满7天只发一次"""
    # 查是否已发过（防止重复发）
    records = feishu_list_records(TICKET_TABLE_ID)
    for item in records:
        f = item.get('fields', {})
        if (f.get('openid') or '').strip() == openid and (f.get('类型') or '') == TICKET_RULES['type']:
            # 已发过同类型门票，不重复发
            return None
    # 生成唯一核销码
    code = None
    for _ in range(100):
        candidate = str(random.randint(10000000, 99999999))
        if not any((item.get('fields', {}).get('核销码') or '').strip() == candidate for item in records):
            code = candidate
            break
    if not code:
        return None
    today = datetime.date.today().strftime('%Y-%m-%d')
    feishu_add_record(TICKET_TABLE_ID, {
        '核销码': code,
        'openid': openid,
        '类型': TICKET_RULES['type'],
        '领取日期': today,
        '状态': '未使用',
        '核销时间': ''
    })
    return {'code': code, 'type': TICKET_RULES['type']}


def get_my_tickets(openid):
    records = feishu_list_records(TICKET_TABLE_ID)
    out = []
    for item in records:
        f = item.get('fields', {})
        if (f.get('openid') or '').strip() == openid:
            out.append({
                'code': f.get('核销码', ''),
                'type': f.get('类型', ''),
                'status': f.get('状态', ''),
                'date': f.get('领取日期', ''),
                'verify_time': f.get('核销时间', '')
            })
    return out


def verify_ticket(code):
    """核销门票。返回 (ok, msg)"""
    records = feishu_list_records(TICKET_TABLE_ID)
    target = None
    for item in records:
        f = item.get('fields', {})
        if (f.get('核销码') or '').strip() == code.strip():
            target = item
            break
    if not target:
        return (False, '无效的核销码')
    f = target.get('fields', {})
    status = (f.get('状态') or '').strip()
    if status == '已使用':
        return (False, '该门票已核销过，请勿重复核销')

    # 使用限制检查（后续改 TICKET_RULES 即可）
    # 这里留空，无限制

    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    feishu_update_record(TICKET_TABLE_ID, target['record_id'], {
        '状态': '已使用',
        '核销时间': now_str
    })
    return (True, '核销成功')


# ============ 微信消息回调（token机制） ============
_tokens = {}   # token -> {'openid': xxx, 'expire': timestamp}

def gen_token(openid):
    token = uuid.uuid4().hex[:16]
    _tokens[token] = {'openid': openid, 'expire': time.time() + 300}
    return token

def get_openid_by_token(token):
    info = _tokens.get(token)
    if not info or info['expire'] < time.time():
        return None
    return info['openid']

def verify_wx_signature(signature, timestamp, nonce):
    tmp = sorted([WX_TOKEN, timestamp, nonce])
    tmp_str = ''.join(tmp)
    return hashlib.sha1(tmp_str.encode()).hexdigest() == signature

def build_reply_xml(to_user, from_user, content):
    """构造微信被动回复文本消息"""
    return ('<xml><ToUserName><![CDATA[' + to_user + ']]></ToUserName>'
            '<FromUserName><![CDATA[' + from_user + ']]></FromUserName>'
            '<CreateTime>' + str(int(time.time())) + '</CreateTime>'
            '<MsgType><![CDATA[text]]></MsgType>'
            '<Content><![CDATA[' + content + ']]></Content></xml>')


def handle_signin_message(from_user, to_user):
    """处理签到消息，返回回复 XML"""
    info = get_signin_info(from_user)
    if info['today_signed']:
        content = ('今日已签到！已连续 ' + str(info['streak']) + ' 天\n'
                   '查看详情：https://shudashui.com/signin.html?token=' + gen_token(from_user))
        return build_reply_xml(from_user, to_user, content)

    # 执行签到
    result = do_signin(from_user)
    streak = result['streak']
    content = '✅ 签到成功！已连续 ' + str(streak) + ' 天'
    if result['ticket']:
        content += ('\n\n🎉 恭喜获得「' + result['ticket']['type'] + '」！'
                    '\n核销码：' + result['ticket']['code'])
    content += '\n\n查看详情：https://shudashui.com/signin.html?token=' + gen_token(from_user)
    return build_reply_xml(from_user, to_user, content)


def handle_text_message(from_user, to_user, content):
    """处理其他文本消息"""
    text = content.strip()
    if '签到' in text:
        return handle_signin_message(from_user, to_user)
    reply = ('欢迎关注书答水！\n\n'
             '回复「签到」领取今日签到\n'
             '连续签到 7 天，免费领「全天不限时畅玩门票」')
    return build_reply_xml(from_user, to_user, reply)


SUCCESS_PAGE = '<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>OK</title><style>body{display:flex;justify-content:center;align-items:center;min-height:100vh;background:linear-gradient(135deg,#667eea,#764ba2);font-family:sans-serif}.box{text-align:center;padding:40px;background:#fff;border-radius:16px;box-shadow:0 20px 60px rgba(0,0,0,.2);max-width:320px;width:90%}.icon{font-size:60px}h1{color:#333}p{color:#777}a{display:block;margin-top:24px;padding:12px;background:#667eea;color:#fff;border-radius:8px;text-decoration:none}</style></head><body><div class="box"><div class="icon">OK</div><h1>预约成功</h1><p>请保留好手环，在预约时间内游玩项目</p><a href="javascript:history.back()">返回</a></div></body></html>'


# ============ 路由 ============
@app.route('/')
def home():
    return 'OK'


@app.route('/api/occupied', methods=['GET', 'OPTIONS'])
def occupied():
    if request.method == 'OPTIONS':
        return ('', 204)
    load_from_feishu()
    room = request.args.get('room', '')
    date = request.args.get('date', '')
    occ = _bookings.get(room, {}).get(date, [])
    return jsonify({'occupied': occ})


@app.route('/api/booking', methods=['POST', 'GET', 'OPTIONS'])
def booking():
    if request.method == 'OPTIONS':
        return ('', 204)
    if request.method == 'GET':
        return 'OK'
    load_from_feishu()
    data = request.form.to_dict() or {}
    code = (data.get('code') or '').strip()
    room = (data.get('roomName') or '').strip()
    date = (data.get('date') or '').strip()
    time_val = (data.get('time') or '').strip()
    remark = (data.get('remark') or '').strip()
    if not code or not room or not date or not time_val:
        return ('<h2>请填写完整信息</h2>', 400)
    if len(code) != 4 or not code.isdigit():
        return ('<h2>手环编号需为4位数字</h2>', 400)
    if time_val in _bookings.get(room, {}).get(date, []):
        return ('<h2>提交失败</h2><p>该时段已被预约。</p>', 400)
    if code in _codes.get(room, {}).get(date, {}):
        return ('<h2>提交失败</h2><p>该手环编号已预约该项目，不能重复预约。</p>', 400)
    try:
        result = write_feishu(data)
        if result.get('code') != 0:
            return ('<h2>提交失败</h2><p>飞书错误: ' + str(result.get('msg')) + '</p>', 500)
        _bookings.setdefault(room, {}).setdefault(date, []).append(time_val)
        if code:
            _codes.setdefault(room, {}).setdefault(date, {})[code] = True
        save_cache()
        return SUCCESS_PAGE
    except Exception as e:
        log('/api/booking err: ' + str(e))
        return ('<h2>提交失败</h2><p>' + str(e) + '</p>', 500)


# ---- 微信消息回调（订阅号开发者模式） ----
@app.route('/api/wx/callback', methods=['GET', 'POST'])
def wx_callback():
    if request.method == 'GET':
        # 服务器验证
        signature = request.args.get('signature', '')
        timestamp = request.args.get('timestamp', '')
        nonce = request.args.get('nonce', '')
        echostr = request.args.get('echostr', '')
        if verify_wx_signature(signature, timestamp, nonce):
            return echostr
        return 'verify fail'

    # POST：接收消息
    try:
        root = ET.fromstring(request.data)
        msg_type = root.find('MsgType').text
        from_user = root.find('FromUserName').text
        to_user = root.find('ToUserName').text
        if msg_type == 'text':
            content = root.find('Content').text
            return handle_text_message(from_user, to_user, content)
        elif msg_type == 'event':
            event = root.find('Event').text
            if event == 'subscribe':
                reply = ('欢迎关注书答水！\n\n'
                         '回复「签到」领取今日签到\n'
                         '连续签到 7 天，免费领「全天不限时畅玩门票」')
                return build_reply_xml(from_user, to_user, reply)
            return 'success'
        return 'success'
    except Exception as e:
        log('wx callback err: ' + str(e))
        return 'success'


# ---- 签到信息查询（token 换身份） ----
@app.route('/api/signin/view', methods=['GET', 'OPTIONS'])
def signin_view():
    if request.method == 'OPTIONS':
        return ('', 204)
    token = request.args.get('token', '')
    openid = get_openid_by_token(token)
    if not openid:
        return jsonify({'ok': False, 'msg': '链接已失效，请重新签到获取'})
    try:
        info = get_signin_info(openid)
        tickets = get_my_tickets(openid)
        return jsonify({
            'ok': True,
            'today_signed': info['today_signed'],
            'streak': info['streak'],
            'need_days': TICKET_RULES['signin_days_needed'],
            'tickets': tickets
        })
    except Exception as e:
        log('signin view err: ' + str(e))
        return jsonify({'ok': False, 'msg': str(e)})


# ---- 微信 OAuth（保留，服务号可用时备用） ----
@app.route('/api/wx/code2session', methods=['GET', 'OPTIONS'])
def wx_login():
    if request.method == 'OPTIONS':
        return ('', 204)
    code = request.args.get('code', '')
    if not code:
        return jsonify({'ok': False, 'msg': '缺少code'})
    try:
        openid = wx_code2session(code)
        if not openid:
            return jsonify({'ok': False, 'msg': '微信授权失败'})
        return jsonify({'ok': True, 'openid': openid})
    except Exception as e:
        log('wx login err: ' + str(e))
        return jsonify({'ok': False, 'msg': str(e)})


# ---- 签到 ----
@app.route('/api/signin/status', methods=['GET', 'OPTIONS'])
def signin_status():
    if request.method == 'OPTIONS':
        return ('', 204)
    openid = request.args.get('openid', '')
    if not openid:
        return jsonify({'ok': False, 'msg': '缺少openid'})
    try:
        info = get_signin_info(openid)
        tickets = get_my_tickets(openid)
        return jsonify({
            'ok': True,
            'today_signed': info['today_signed'],
            'streak': info['streak'],
            'need_days': TICKET_RULES['signin_days_needed'],
            'tickets': tickets
        })
    except Exception as e:
        log('signin status err: ' + str(e))
        return jsonify({'ok': False, 'msg': str(e)})


@app.route('/api/signin/do', methods=['POST', 'OPTIONS'])
def signin_do():
    if request.method == 'OPTIONS':
        return ('', 204)
    data = request.form.to_dict() or {}
    openid = (data.get('openid') or '').strip()
    if not openid:
        return jsonify({'ok': False, 'msg': '缺少openid'})
    try:
        result = do_signin(openid)
        return jsonify({
            'ok': True,
            'already': result['already'],
            'streak': result['streak'],
            'ticket': result['ticket']
        })
    except Exception as e:
        log('signin do err: ' + str(e))
        return jsonify({'ok': False, 'msg': str(e)})


# ---- 核销 ----
@app.route('/api/ticket/verify', methods=['POST', 'OPTIONS'])
def ticket_verify():
    if request.method == 'OPTIONS':
        return ('', 204)
    data = request.form.to_dict() or {}
    code = (data.get('code') or '').strip()
    if not code:
        return jsonify({'ok': False, 'msg': '请输入核销码'})
    try:
        ok, msg = verify_ticket(code)
        return jsonify({'ok': ok, 'msg': msg})
    except Exception as e:
        log('verify err: ' + str(e))
        return jsonify({'ok': False, 'msg': str(e)})


@app.route('/api/admin/reload', methods=['GET'])
def admin_reload():
    global _bookings, _codes, _initialized, _last_refresh
    _bookings, _codes = {}, {}
    _initialized = False
    _last_refresh = 0
    load_from_feishu(force=True)
    return jsonify({'bookings': _bookings, 'codes': _codes})
