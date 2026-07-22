from flask import Flask, request, jsonify
import json, time, urllib.request

app = Flask(__name__)

FEISHU_APP_ID = 'cli_aaeacecbf47a9bc0'
FEISHU_APP_SECRET = 'UmiNOo8IHbFIb1iLwEaa8gNreIem2nVD'
BASE_ID = 'QXazbngDbamnwGsMjEbc58TGnDh'
TABLE_ID = 'tblRD66BfFKmKQQl'

_token = None
_token_expire = 0


def get_token():
    global _token, _token_expire
    now = time.time()
    if _token and now < _token_expire - 60:
        return _token
    data = json.dumps({'app_id': FEISHU_APP_ID, 'app_secret': FEISHU_APP_SECRET}).encode()
    req = urllib.request.Request(
        'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
        data=data,
        headers={'Content-Type': 'application/json; charset=utf-8'}
    )
    resp = urllib.request.urlopen(req, timeout=10)
    body = json.loads(resp.read())
    _token = body['tenant_access_token']
    _token_expire = now + body.get('expire', 7200)
    return _token


def write_feishu(data):
    token = get_token()
    body = {
        'fields': {
            '称呼': (data.get('name') or '').strip(),
            '电话': (data.get('phone') or '').strip(),
            '项目': (data.get('roomName') or '').strip(),
            '日期': (data.get('date') or '').strip(),
            '时间': (data.get('time') or '').strip(),
            '人数': _to_int(data.get('people')),
            '备注': (data.get('remark') or '').strip()
        }
    }
    url = f'https://open.feishu.cn/open-apis/bitable/v1/apps/{BASE_ID}/tables/{TABLE_ID}/records'
    req = urllib.request.Request(url, data=json.dumps(body).encode('utf-8'), headers={
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json; charset=utf-8'
    })
    resp = urllib.request.urlopen(req, timeout=10)
    return json.loads(resp.read())


def _to_int(v):
    try:
        return int(v)
    except (ValueError, TypeError):
        return 0


@app.after_request
def add_cors(resp):
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    resp.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS, GET'
    return resp


@app.route('/api/booking', methods=['GET', 'POST', 'OPTIONS'])
def booking():
    if request.method == 'OPTIONS':
        return ('', 204)
    if request.method == 'GET':
        return jsonify({'status': 'ok'})

    data = request.get_json(silent=True) or {}
    phone = (data.get('phone') or '').strip()
    room = (data.get('roomName') or '').strip()
    if not phone or not room:
        return jsonify({'code': -1, 'msg': '电话和项目不能为空'}), 400

    try:
        write_feishu(data)
        return jsonify({'code': 0, 'msg': '预约成功'})
    except Exception as e:
        return jsonify({'code': -1, 'msg': str(e)}), 500
