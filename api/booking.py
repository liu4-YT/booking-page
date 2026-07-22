print('=== API LOADED ===')
from flask import Flask, request, jsonify
import time, urllib.request, json

app = Flask(__name__)

# 飞书配置
FS = {
    'id': 'cli_aaeacecbf47a9bc0',
    'sk': 'UmiNOo8IHbFIb1iLwEaa8gNreIem2nVD',
    'base': 'QXazbngDbamnwGsMjEbc58TGnDh',
    'tbl': 'tblRD66BfFKmKQQl'
}
_tk = [None, 0]


def _token():
    if _tk[0] and time.time() < _tk[1] - 60:
        return _tk[0]
    d = json.dumps({'app_id': FS['id'], 'app_secret': FS['sk']}).encode()
    r = urllib.request.Request('https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
                               data=d, headers={'Content-Type': 'application/json; charset=utf-8'})
    b = json.loads(urllib.request.urlopen(r, timeout=10).read())
    _tk[0] = b['tenant_access_token']
    _tk[1] = time.time() + b.get('expire', 7200)
    return _tk[0]


@app.route('/api/booking', methods=['POST', 'OPTIONS'])
def booking():
    if request.method == 'OPTIONS':
        r = jsonify({})
        r.headers['Access-Control-Allow-Origin'] = '*'
        r.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        r.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        return r, 204

    d = request.get_json(silent=True) or {}
    phone = (d.get('phone') or '').strip()
    room = (d.get('roomName') or '').strip()
    if not phone or not room:
        r = jsonify({'code': -1, 'msg': '电话和项目不能为空'})
        r.headers['Access-Control-Allow-Origin'] = '*'
        return r, 400

    try:
        tk = _token()
        body = json.dumps({'fields': {
            '称呼': (d.get('name') or '').strip(),
            '电话': phone,
            '项目': room,
            '日期': (d.get('date') or '').strip(),
            '时间': (d.get('time') or '').strip(),
            '人数': int(d.get('people', 0) or 0),
            '备注': (d.get('remark') or '').strip()
        }}).encode('utf-8')
        url = f'https://open.feishu.cn/open-apis/bitable/v1/apps/{FS["base"]}/tables/{FS["tbl"]}/records'
        req = urllib.request.Request(url, data=body, headers={
            'Authorization': f'Bearer {tk}',
            'Content-Type': 'application/json; charset=utf-8'
        })
        urllib.request.urlopen(req, timeout=10)
        r = jsonify({'code': 0, 'msg': '预约成功'})
        r.headers['Access-Control-Allow-Origin'] = '*'
        return r
    except Exception as e:
        r = jsonify({'code': -1, 'msg': str(e)})
        r.headers['Access-Control-Allow-Origin'] = '*'
        return r, 500
