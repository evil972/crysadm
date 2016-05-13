# Html － 我的矿机
__author__ = 'powergx'
from flask import request, Response, render_template, session, url_for, redirect
from crysadm import app, r_session
from auth import requires_admin, requires_auth
import json
import requests
from urllib.parse import urlparse, parse_qs, unquote
import time
from datetime import datetime
import re
from api import ubus_cd, collect, exec_draw_cash, api_sys_getEntry, api_steal_search, api_steal_collect, api_steal_summary, api_getaward, get_mine_info

# 加载矿机主页面
@app.route('/excavators')
@requires_auth
def excavators():
    user = session.get('user_info')
    user_key = '%s:%s' % ('user', user.get('username'))
    user_info = json.loads(r_session.get(user_key).decode('utf-8'))

    err_msg = None
    if session.get('error_message') is not None:
        err_msg = session.get('error_message')
        session['error_message'] = None

    info_msg = None
    if session.get('info_message') is not None:
        info_msg = session.get('info_message')
        session['info_message'] = None

    accounts_key = 'accounts:%s' % user.get('username')
    accounts = list()

    id_map = {}
    for acct in sorted(r_session.smembers(accounts_key)):
        account_key = 'account:%s:%s' % (user.get('username'), acct.decode("utf-8"))
        account_data_key = account_key + ':data'
        account_data_value = r_session.get(account_data_key)
        account_info = json.loads(r_session.get(account_key).decode("utf-8"))
        if account_data_value is not None:
            account_info['data'] = json.loads(account_data_value.decode("utf-8"))
        if 'root_passwd' in user_info.keys() and 'data' in account_info.keys() and 'device_info' in account_info['data'].keys():
            for dev in account_info['data']['device_info']:
                if dev['device_id'] in user_info['root_passwd'].keys():
                    dev['password']=user_info['root_passwd'][dev['device_id']]
        accounts.append(account_info)
        if user_info.get('is_show_byname') == 0:
            id_map[account_info.get('user_id')]=account_info.get('remark_name')
        elif user_info.get('is_show_byname') == 1:
            id_map[account_info.get('user_id')]=account_info.get('account_name')
        else:
            id_map[account_info.get('user_id')]=account_info.get('username')

    show_drawcash = not (r_session.get('can_drawcash') is None or
                         r_session.get('can_drawcash').decode('utf-8') == '0')

    return render_template('excavators.html', err_msg=err_msg, info_msg=info_msg, accounts=accounts,
                           show_drawcash=show_drawcash, id_map=id_map)

# 正则过滤+URL转码
def regular_html(info):
    regular = re.compile('<[^>]+>')
    url = unquote(info)
    return regular.sub("", url)

# 手动日记记录
def red_log(clas, type, id, gets):
    user = session.get('user_info')

    record_key = '%s:%s' % ('record', user.get('username'))
    record_info = json.loads(r_session.get(record_key).decode('utf-8'))

    log_as_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    body = dict(time=log_as_time, clas=clas, type=type, id=id, gets=gets)

    log_as_body = record_info.get('diary')
    log_trimed = []
    for item in log_as_body:
       if (datetime.now() - datetime.strptime(item.get('time'), '%Y-%m-%d %H:%M:%S')).days < 31:
           log_trimed.append(item)
    log_trimed.append(body)

    record_info['diary'] = log_trimed

    r_session.set(record_key, json.dumps(record_info))

# 收取水晶[id]
@app.route('/collect/<user_id>', methods=['POST'])
@requires_auth
def collect_id(user_id):
    user = session.get('user_info')
    account_key = 'account:%s:%s' % (user.get('username'), user_id)
    account_info = json.loads(r_session.get(account_key).decode("utf-8"))

    session_id = account_info.get('session_id')
    user_id = account_info.get('user_id')

    cookies = dict(sessionid=session_id, userid=str(user_id))

    mine_info = get_mine_info(cookies)
    r = collect(cookies)
    if r.get('rd') != 'ok':
        log = '%s' % r.get('rd')
        session['error_message'] = log
        return redirect(url_for('excavators'))
    else:
        log = '收取:%s水晶.' % mine_info.get('td_not_in_a')
        session['info_message'] = log
    red_log('手动执行', '收取', user_id, log)
    account_data_key = account_key + ':data'
    account_data_value = json.loads(r_session.get(account_data_key).decode("utf-8"))
    account_data_value.get('mine_info')['td_not_in_a'] = 0
    r_session.set(account_data_key, json.dumps(account_data_value))

    return redirect(url_for('excavators'))

# 收取水晶[all]
@app.route('/collect/all', methods=['POST'])
@requires_auth
def collect_all():
    user = session.get('user_info')
    username = user.get('username')

    error_message = ''
    success_message = ''
    for b_user_id in r_session.smembers('accounts:%s' % username):

        account_key = 'account:%s:%s' % (username, b_user_id.decode("utf-8"))
        account_info = json.loads(r_session.get(account_key).decode("utf-8"))

        session_id = account_info.get('session_id')
        user_id = account_info.get('user_id')

        cookies = dict(sessionid=session_id, userid=str(user_id))
        mine_info = get_mine_info(cookies)
        time.sleep(1)
        r = collect(cookies)
        if r.get('rd') != 'ok':
            log = '%s' % r.get('rd')
            error_message += 'Id:%s : %s<br />' % (user_id, r.get('rd'))
        else:
            log = '收取:%s水晶.' % mine_info.get('td_not_in_a')
            success_message += 'Id:%s : 收取:%s水晶.<br />' % (user_id,mine_info.get('td_not_in_a'))
            account_data_key = account_key + ':data'
            account_data_value = json.loads(r_session.get(account_data_key).decode("utf-8"))
            account_data_value.get('mine_info')['td_not_in_a'] = 0
            r_session.set(account_data_key, json.dumps(account_data_value))
        red_log('手动执行', '收取', user_id, log)

    if len(success_message) > 0:
        session['info_message'] = success_message

    if len(error_message) > 0:
        session['error_message'] = error_message

    return redirect(url_for('excavators'))

# 幸运转盘[id]
@app.route('/getaward/<user_id>', methods=['POST'])
@requires_auth
def getaward_id(user_id):
    user = session.get('user_info')
    account_key = 'account:%s:%s' % (user.get('username'), user_id)
    account_info = json.loads(r_session.get(account_key).decode("utf-8"))

    session_id = account_info.get('session_id')
    user_id = account_info.get('user_id')

    cookies = dict(sessionid=session_id, userid=str(user_id))
    r = api_getaward(cookies)
    if r.get('rd') != 'ok':
        session['error_message'] = r.get('rd')
        red_log('手动执行', '转盘', user_id, r.get('rd'))
        return redirect(url_for('excavators'))
    else:
        session['info_message'] = '获得:%s  下次转需要:%s秘银.<br />' % (regular_html(r.get('tip')), r.get('cost'))
        red_log('手动执行', '转盘', user_id, '获得:%s' % regular_html(r.get('tip')))
    account_data_key = account_key + ':data'
    account_data_value = json.loads(r_session.get(account_data_key).decode("utf-8"))
    account_data_value.get('mine_info')['td_not_in_a'] = 0
    r_session.set(account_data_key, json.dumps(account_data_value))

    return redirect(url_for('excavators'))

# 幸运转盘[all]
@app.route('/getaward/all', methods=['POST'])
@requires_auth
def getaward_all():
    user = session.get('user_info')
    username = user.get('username')

    error_message = ''
    success_message = ''
    for b_user_id in r_session.smembers('accounts:%s' % username):

        account_key = 'account:%s:%s' % (username, b_user_id.decode("utf-8"))
        account_info = json.loads(r_session.get(account_key).decode("utf-8"))

        session_id = account_info.get('session_id')
        user_id = account_info.get('user_id')

        cookies = dict(sessionid=session_id, userid=str(user_id))
        r = api_getaward(cookies)
        if r.get('rd') != 'ok':
            error_message += 'Id:%s : %s<br />' % (user_id, r.get('rd'))
            red_log('手动执行', '转盘', user_id, r.get('rd'))
        else:
            success_message += 'Id:%s : 获得:%s  下次转需要:%s 秘银.<br />' % (user_id, regular_html(r.get('tip')), r.get('cost'))
            red_log('手动执行', '转盘', user_id, '获得:%s' % regular_html(r.get('tip')))
            account_data_key = account_key + ':data'
            account_data_value = json.loads(r_session.get(account_data_key).decode("utf-8"))
            account_data_value.get('mine_info')['td_not_in_a'] = 0
            r_session.set(account_data_key, json.dumps(account_data_value))
    if len(success_message) > 0:
        session['info_message'] = success_message

    if len(error_message) > 0:
        session['error_message'] = error_message

    return redirect(url_for('excavators'))

# 秘银进攻[id]
@app.route('/searcht/<user_id>', methods=['POST'])
@requires_auth
def searcht_id(user_id):
    user = session.get('user_info')
    account_key = 'account:%s:%s' % (user.get('username'), user_id)
    account_info = json.loads(r_session.get(account_key).decode("utf-8"))

    session_id = account_info.get('session_id')
    user_id = account_info.get('user_id')

    cookies = dict(sessionid=session_id, userid=str(user_id))
    r = check_searcht(cookies)
    if r.get('r') != 0:
        session['error_message'] = regular_html(r.get('rd'))
        red_log('手动执行', '进攻', user_id, regular_html(r.get('rd')))
        return redirect(url_for('excavators'))
    else:
        session['info_message'] = '获得:%s秘银.' % r.get('s')
        red_log('手动执行', '进攻', user_id, '获得:%s秘银.' % r.get('s'))
    account_data_key = account_key + ':data'
    account_data_value = json.loads(r_session.get(account_data_key).decode("utf-8"))
    account_data_value.get('mine_info')['td_not_in_a'] = 0
    r_session.set(account_data_key, json.dumps(account_data_value))

    return redirect(url_for('excavators'))

# 秘银进攻[all]
@app.route('/searcht/all', methods=['POST'])
@requires_auth
def searcht_all():
    user = session.get('user_info')
    username = user.get('username')

    error_message = ''
    success_message = ''
    for b_user_id in r_session.smembers('accounts:%s' % username):

        account_key = 'account:%s:%s' % (username, b_user_id.decode("utf-8"))
        account_info = json.loads(r_session.get(account_key).decode("utf-8"))

        session_id = account_info.get('session_id')
        user_id = account_info.get('user_id')

        cookies = dict(sessionid=session_id, userid=str(user_id))
        r = check_searcht(cookies)
        if r.get('r') != 0:
            error_message += 'Id:%s : %s<br />' % (user_id, regular_html(r.get('rd')))
            red_log('手动执行', '进攻', user_id, regular_html(r.get('rd')))
        else:
            success_message += 'Id:%s : 获得:%s秘银.<br />' % (user_id, r.get('s'))
            red_log('手动执行', '进攻', user_id, '获得:%s秘银.' % r.get('s'))
            account_data_key = account_key + ':data'
            account_data_value = json.loads(r_session.get(account_data_key).decode("utf-8"))
            account_data_value.get('mine_info')['td_not_in_a'] = 0
            r_session.set(account_data_key, json.dumps(account_data_value))
    if len(success_message) > 0:
        session['info_message'] = success_message

    if len(error_message) > 0:
        session['error_message'] = error_message

    return redirect(url_for('excavators'))

# 执行进攻函数
def check_searcht(cookies):
    t = api_sys_getEntry(cookies)
    if t.get('r') != 0:
        return dict(r='-1', rd='Forbidden')
    if t.get('steal_free') > 0:
        steal_info = api_steal_search(cookies)
        if steal_info.get('r') != 0:
            return steal_info
        r = api_steal_collect(cookies=cookies, searcht_id=steal_info.get('sid'))
        if r.get('r') != 0:
            return dict(r='-1', rd='Forbidden')
        api_steal_summary(cookies=cookies, searcht_id=steal_info.get('sid'))
        return r
    return dict(r='-1', rd='体力值为零')

# 用户提现[id]
@app.route('/drawcash/<user_id>', methods=['POST'])
@requires_auth
def drawcash_id(user_id):
    user = session.get('user_info')
    account_key = 'account:%s:%s' % (user.get('username'), user_id)
    account_info = json.loads(r_session.get(account_key).decode("utf-8"))

    session_id = account_info.get('session_id')
    user_id = account_info.get('user_id')

    cookies = dict(sessionid=session_id, userid=str(user_id))
    r = exec_draw_cash(cookies)
    if r.get('r') != 0:
        session['error_message'] = r.get('rd')
        return redirect(url_for('excavators'))
    else:
        session['info_message'] = r.get('rd')
    account_data_key = account_key + ':data'
    account_data_value = json.loads(r_session.get(account_data_key).decode("utf-8"))
    account_data_value.get('income')['r_can_use'] = 0
    r_session.set(account_data_key, json.dumps(account_data_value))

    return redirect(url_for('excavators'))

# 用户提现[all]
@app.route('/drawcash/all', methods=['POST'])
@requires_auth
def drawcash_all():
    user = session.get('user_info')
    username = user.get('username')

    error_message = ''
    success_message = ''
    for b_user_id in r_session.smembers('accounts:%s' % username):

        account_key = 'account:%s:%s' % (username, b_user_id.decode("utf-8"))
        account_info = json.loads(r_session.get(account_key).decode("utf-8"))

        session_id = account_info.get('session_id')
        user_id = account_info.get('user_id')

        cookies = dict(sessionid=session_id, userid=str(user_id))
        r = exec_draw_cash(cookies)
        if r.get('r') != 0:
            error_message += 'Id:%s : %s<br />' % (user_id, r.get('rd'))
        else:
            success_message += 'Id:%s : %s<br />' % (user_id, r.get('rd'))
            account_data_key = account_key + ':data'
            account_data_value = json.loads(r_session.get(account_data_key).decode("utf-8"))
            account_data_value.get('income')['r_can_use'] = 0
            r_session.set(account_data_key, json.dumps(account_data_value))
    if len(success_message) > 0:
        session['info_message'] = success_message

    if len(error_message) > 0:
        session['error_message'] = error_message

    return redirect(url_for('excavators'))

# 暂停设备按钮
@app.route('/stop_device', methods=['POST'])
@requires_auth
def stop_device():
    device_id = request.values.get('device_id')
    session_id = request.values.get('session_id')
    account_id = request.values.get('account_id')

    ubus_cd(session_id, account_id, 'check', ["dcdn", "stop", {}], '&device_id=%s' % device_id)

    return redirect(url_for('excavators'))

# 启动设备按钮
@app.route('/start_device', methods=['POST'])
@requires_auth
def start_device():
    device_id = request.values.get('device_id')
    session_id = request.values.get('session_id')
    account_id = request.values.get('account_id')

    ubus_cd(session_id, account_id, 'check', ["dcdn", "start", {}], '&device_id=%s' % device_id)

    return redirect(url_for('excavators'))

# 升级设备按钮
@app.route('/upgrade_device', methods=['POST'])
@requires_auth
def upgrade_device():
    device_id = request.values.get('device_id')
    session_id = request.values.get('session_id')
    account_id = request.values.get('account_id')

    ubus_cd(session_id, account_id, 'get_progress', ["upgrade", "start", {}], '&device_id=%s' % device_id)
    ubus_cd(session_id, account_id, 'get_progress', ["upgrade", "get_progress", {}], '&device_id=%s' % device_id)

    return redirect(url_for('excavators'))

# 重启设备按钮
@app.route('/reboot_device', methods=['POST'])
@requires_auth
def reboot_device():
    device_id = request.values.get('device_id')
    session_id = request.values.get('session_id')
    account_id = request.values.get('account_id')

    ubus_cd(session_id, account_id, 'reboot', ["mnt", "reboot", {}], '&device_id=%s' % device_id)

    return redirect(url_for('excavators'))

# 恢复出厂设置设备按钮
@app.route('/reset_device', methods=['POST'])
@requires_auth
def reset_device():
    device_id = request.values.get('device_id')
    session_id = request.values.get('session_id')
    account_id = request.values.get('account_id')

    ubus_cd(session_id, account_id, 'reset', ["mnt", "reset", {}], '&device_id=%s' % device_id)

    return redirect(url_for('excavators'))

# 定位设备按钮
@app.route('/noblink_device', methods=['POST'])
@requires_auth
def noblink_device():
    device_id = request.values.get('device_id')
    session_id = request.values.get('session_id')
    account_id = request.values.get('account_id')

    for i in range(10):# 循环20次
        ubus_cd(session_id, account_id, 'noblink', ["mnt", "noblink", {}], '&device_id=%s' % device_id)#闪
        time.sleep(2)
        ubus_cd(session_id, account_id, 'blink', ["mnt", "blink", {}], '&device_id=%s' % device_id)#不闪

    return redirect(url_for('excavators'))

# 生成设备名称
@app.route('/set_device_name', methods=['POST'])
@requires_auth
def set_device_name():
    setting_url = request.values.get('url')
    new_name = request.values.get('name')
    query_s = parse_qs(urlparse(setting_url).query, keep_blank_values=True)

    device_id = query_s['device_id'][0]
    session_id = query_s['session_id'][0]
    account_id = query_s['user_id'][0]

    ubus_cd(session_id, account_id, 'set_device_name',
            ["server", "set_device_name", {"device_name": new_name, "device_id": device_id}])

    return json.dumps(dict(status='success'))

# 计算设备ROOT密码
# ROOT技术提供：掌柜
# 显著位置
# http://www.renyiai.com
# 显著位置
@app.route('/admin_root', methods=['POST'])
@requires_auth
def admin_root():
    import hashlib
    import base64
    user = session.get('user_info')
    user_key = '%s:%s' % ('user', user.get('username'))
    user_info = json.loads(r_session.get(user_key).decode('utf-8'))
    action = None
    if session.get('action') is not None:
        action = session.get('action')
        session['action'] = None
    if 'root_no' in user_info.keys() and user_info['root_no'] > 0:
        device_id = request.values.get('device_id')
        session_id = request.values.get('session_id')
        account_id = request.values.get('account_id')
        dev = ubus_cd(session_id, account_id, 'get_device', ["server", "get_device", {"device_id": device_id}])
        if dev is not None:
            if 'result' in dev.keys():
                sn=dev['result'][1]['device_sn']
                mac=dev['result'][1]['mac_address']
                key='%s%s%s'%(sn,mac,'i8e%Fvj24nz024@d!c')
                m=hashlib.md5()
                m.update(key.encode('utf-8'))
                md5=m.digest()
                passwd=base64.b64encode(md5).decode('utf-8')
                passwd=passwd[0:8]
                passwd=passwd.replace('+','-')
                passwd=passwd.replace('/','_')
                if 'root_passwd' not in user_info.keys():
                    user_info['root_passwd']={}
                user_info['root_passwd'][device_id]=passwd
                user_info['root_no']=user_info['root_no'] - 1
                r_session.set(user_key, json.dumps(user_info))
            else:
                session['error_message']='获取ROOT所需信息失败'
        else:
            session['error_message']='请选择一个需要ROOT密码的设备'
        return redirect(url_for('excavators'))
    session['error_message']='您的账户没有ROOT机会了，请联系管理员获取。'
    return redirect(url_for('excavators'))

# 加载设备页面
@app.route('/admin_device', methods=['POST'])
@requires_auth
def admin_device():
    user = session.get('user_info')

    action = None
    if session.get('action') is not None:
        action = session.get('action')
        session['action'] = None

    device_id = request.values.get('device_id')
    session_id = request.values.get('session_id')
    account_id = request.values.get('account_id')

    dev = ubus_cd(session_id, account_id, 'get_device', ["server", "get_device", {"device_id": device_id}])

    return render_template('excavators_info.html', action=action, device_id=device_id, session_id=session_id, account_id=account_id, dev=dev)
