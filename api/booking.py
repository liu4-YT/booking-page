from flask import Flask, request, jsonify
import requests
import time

app = Flask(__name__)

# CORS 支持（允许预约页跨域 POST）
@app.after_request
def add_cors(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
    return response

# 飞书配置
FEISHU_APP_ID = 'cli_aaeacecbf47a9bc0'
FEISHU_APP_SECRET = 'UmiNOo8IHbFIb1iLwEaa8gNreIem2nVD'
BASE_ID = 'QXazbngDbamnwGsMjEbc58TGnDh'
TABLE_ID = 'tblRD66BfFKmKQQl'

# Token 缓存
_token = None
_token_expire = 0

def get_token():
    global _token, _token_expire
    now = time.time()
    if _token and now < _token_expire - 60:
        return _token
    r = requests.post(
        'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
        json={'app_id': FEISHU_APP_ID, 'app_secret': FEISHU_APP_SECRET},
        timeout=10
    )
    data = r.json()
    _token = data['tenant_access_token']
    _token_expire = now + data.get('expire', 7200)
    return _token

@app.route('/api/booking', methods=['POST'])
def booking():
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({'code': -1, 'msg': '数据格式错误'}), 400

    # 提取字段
    name = (data.get('name') or '').strip()
    phone = (data.get('phone') or '').strip()
    room = (data.get('roomName') or '').strip()
    date = (data.get('date') or '').strip()
    time_val = (data.get('time') or '').strip()
    people = data.get('people', '')
    remark = (data.get('remark') or '').strip()

    if not phone or not room:
        return jsonify({'code': -1, 'msg': '电话和项目不能为空'}), 400

    try:
        token = get_token()
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json; charset=utf-8'
        }
        body = {
            'fields': {
                '称呼': name,
                '电话': phone,
                '项目': room,
                '日期': date,
                '时间': time_val,
                '人数': int(people) if people else 0,
                '备注': remark
            }
        }
        url = f'https://open.feishu.cn/open-apis/bitable/v1/apps/{BASE_ID}/tables/{TABLE_ID}/records'
        r = requests.post(url, headers=headers, json=body, timeout=10)
        resp = r.json()
        if resp.get('code') != 0:
            return jsonify({'code': -1, 'msg': f'飞书写入失败: {resp.get("msg")}'}), 500

        return jsonify({'code': 0, 'msg': '预约成功'})
    except Exception as e:
        return jsonify({'code': -1, 'msg': f'服务器错误: {str(e)}'}), 500

# Vercel 入口
def handler(environ, start_response):
    return app(environ, start_response)
