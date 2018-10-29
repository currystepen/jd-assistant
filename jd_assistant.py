#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re
import random
from datetime import datetime
from urllib import parse

import pickle
from bs4 import BeautifulSoup

from jd_tools import *


class Assistant(object):

    def __init__(self):
        self.username = ''
        self.nick_name = ''
        self.is_login = False
        self.risk_control = ''
        self.item_cat = dict()
        self.default_addr = None
        self.seckill_data = None
        self.seckill_url = ''
        self.eid = 'UHU6KVDJS7PNLJUHG2ICBFACVLMEXVPQUGIK2QVXYMSN45BIEMUSICVLTYQYOZYZN2KWHV3WQWMFH4QPED2DVQHUXE'
        self.fp = '536e2679b85ddea9baccc7b705f2f8e0'
        self.headers = {
            'Host': 'passport.jd.com',
            'Connection': 'keep-alive',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.181 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        }
        self.sess = requests.session()
        try:
            self._load_cookies()
        except Exception as e:
            pass

    def _load_cookies(self):
        cookies_file = ''
        for name in os.listdir('./cookies'):
            if name.endswith('.cookies'):
                cookies_file = './cookies/{0}'.format(name)
                break
        with open(cookies_file, 'rb') as f:
            local_cookies = pickle.load(f)
        self.sess.cookies.update(local_cookies)
        self.is_login = self._validate_cookies()

    def _save_cookies(self):
        cookies_file = './cookies/{0}.cookies'.format(self.nick_name)
        directory = os.path.dirname(cookies_file)
        if not os.path.exists(directory):
            os.makedirs(directory)
        with open(cookies_file, 'wb') as f:
            pickle.dump(self.sess.cookies, f)

    def _validate_cookies(self):  # True -- cookies is valid, False -- cookies is invalid
        # user can't access to order list page (would redirect to login page) if his cookies is expired
        url = 'https://order.jd.com/center/list.action'
        payload = {
            'rid': str(int(time.time() * 1000)),
        }
        try:
            resp = self.sess.get(url=url, params=payload, allow_redirects=False)
            return True if resp.status_code == requests.codes.OK else False
        except Exception as e:
            print(get_current_time(), e)
            return False

    def _need_auth_code(self, username):
        url = 'https://passport.jd.com/uc/showAuthCode'
        data = {
            'loginName': username,
        }
        payload = {
            'version': 2015,
            'r': random.random(),
        }
        resp = self.sess.post(url, params=payload, data=data, headers=self.headers)
        if not response_status(resp):
            print('获取是否需要验证码失败')
            return False

        js = json.loads(resp.text[1:-1])  # ({"verifycode":true})
        return js['verifycode']

    def _get_auth_code(self, uuid):
        image_file = os.path.join(os.getcwd(), 'jd_authcode.jpg')

        url = 'https://authcode.jd.com/verify/image'
        payload = {
            'a': 1,
            'acid': uuid,
            'uid': uuid,
            'yys': str(int(time.time() * 1000)),
        }
        self.headers['Host'] = 'authcode.jd.com'
        self.headers['Referer'] = 'https://passport.jd.com/uc/login'
        resp = self.sess.get(url, params=payload, headers=self.headers)

        if not response_status(resp):
            print('获取验证码失败')
            return ''

        save_image(resp, image_file)
        open_image(image_file)
        return input('验证码:')

    def _get_login_page(self):
        url = "https://passport.jd.com/new/login.aspx"
        page = self.sess.get(url, headers=self.headers)
        return page

    def _get_login_data(self):
        page = self._get_login_page()
        soup = BeautifulSoup(page.text, "html.parser")
        input_list = soup.select('.form input')

        data = dict()
        data['sa_token'] = input_list[0]['value']
        data['uuid'] = input_list[1]['value']
        data['_t'] = input_list[4]['value']
        data['loginType'] = input_list[5]['value']
        data['pubKey'] = input_list[7]['value']
        # eid & fp are generated by local javascript code according to browser environment
        data['eid'] = self.eid
        data['fp'] = self.fp
        return data

    def login_by_username(self):
        if self.is_login:
            print(get_current_time(), '登录成功')
            return

        username = input('账号:')
        password = input('密码:')
        if (not username) or (not password):
            print(get_current_time(), '用户名或密码不能为空')
            return
        self.username = username

        data = self._get_login_data()
        uuid = data['uuid']

        auth_code = ''
        if self._need_auth_code(username):
            print(get_current_time(), '本次登录需要验证码')
            auth_code = self._get_auth_code(uuid)
        else:
            print(get_current_time(), '本次登录不需要验证码')

        login_url = "https://passport.jd.com/uc/loginService"
        payload = {
            'uuid': uuid,
            'version': 2015,
            'r': random.random(),
        }
        data['authcode'] = auth_code
        data['loginname'] = username
        data['nloginpwd'] = encrypt_pwd(password)
        self.headers['Host'] = 'passport.jd.com'
        self.headers['Origin'] = 'https://passport.jd.com'
        self.headers['X-Requested-With'] = 'XMLHttpRequest'
        resp = self.sess.post(url=login_url, data=data, headers=self.headers, params=payload)

        if not response_status(resp):
            print(get_current_time(), '登录失败')
            return False

        if not self._get_login_result(resp):
            return False

        # login success
        print(get_current_time(), '登录成功')
        self.nick_name = self.get_user_info()
        self._save_cookies()
        self.is_login = True
        return True

    def _get_login_result(self, resp):
        js = parse_json(resp.text)
        error_msg = ''
        if 'success' in js:
            # {"success":"http://www.jd.com"}
            return True
        elif 'emptyAuthcode' in js:
            # {'_t': '_t', 'emptyAuthcode': '请输入验证码'}
            # {'_t': '_t', 'emptyAuthcode': '验证码不正确或验证码已过期'}
            error_msg = js['emptyAuthcode']
        elif 'username' in js:
            # {'_t': '_t', 'username': '账户名不存在，请重新输入'}
            # {'username': '服务器繁忙，请稍后再试', 'venture': 'xxxx', 'p': 'xxxx', 'ventureRet': 'http://www.jd.com/', '_t': '_t'}
            if js['username'] == '服务器繁忙，请稍后再试':
                error_msg = js['username'] + '(预计账户存在风险，需短信激活)'
            else:
                error_msg = js['username']
        elif 'pwd' in js:
            # {'pwd': '账户名与密码不匹配，请重新输入', '_t': '_t'}
            error_msg = js['pwd']
        else:
            error_msg = js
        print(get_current_time(), error_msg)
        return False

    def _get_QRcode(self):
        url = 'https://qr.m.jd.com/show'
        self.headers['Host'] = 'qr.m.jd.com'
        self.headers['Referer'] = 'https://passport.jd.com/new/login.aspx'
        payload = {
            'appid': 133,
            'size': 147,
            't': str(int(time.time() * 1000)),
        }
        resp = self.sess.get(url=url, headers=self.headers, params=payload)

        if not response_status(resp):
            print(get_current_time(), '获取二维码失败')
            return False

        QRCode_file = 'QRcode.png'
        save_image(resp, QRCode_file)
        print(get_current_time(), '验证码获取成功，请打开京东APP扫描')
        open_image(QRCode_file)
        return True

    def _get_QRcode_ticket(self):
        url = 'https://qr.m.jd.com/check'
        payload = {
            'appid': '133',
            'callback': 'jQuery{}'.format(random.randint(1000000, 9999999)),
            'token': self.sess.cookies.get('wlfstk_smdl'),
            '_': str(int(time.time() * 1000)),
        }
        resp = self.sess.get(url=url, headers=self.headers, params=payload)

        if not response_status(resp):
            print(get_current_time(), '获取二维码扫描结果出错')
            return False

        js = parse_json(resp.text)
        if js['code'] != 200:
            print(get_current_time(), 'Code: {0}, Message: {1}'.format(js['code'], js['msg']))
            return None
        else:
            print(get_current_time(), '已完成手机客户端确认')
            return js['ticket']

    def _validate_QRcode_ticket(self, ticket):
        url = 'https://passport.jd.com/uc/qrCodeTicketValidation'
        self.headers['Host'] = 'passport.jd.com'
        self.headers['Referer'] = 'https://passport.jd.com/uc/login?ltype=logout'
        resp = self.sess.get(url=url, headers=self.headers, params={'t': ticket})

        if not response_status(resp):
            return False

        js = json.loads(resp.text)
        if js['returnCode'] == 0:
            return True
        else:
            print(get_current_time(), js)
            return False

    def login_by_QRcode(self):
        if self.is_login:
            print(get_current_time(), '登录成功')
            return True

        self._get_login_page()

        # download QR code
        if not self._get_QRcode():
            print(get_current_time(), '登录失败')
            return False

        # get QR code ticket
        ticket = None
        retry_times = 90
        for _ in range(retry_times):
            ticket = self._get_QRcode_ticket()
            if ticket:
                break
            time.sleep(2)
        else:
            print(get_current_time(), '二维码扫描出错')
            return False

        # validate QR code ticket
        if not self._validate_QRcode_ticket(ticket):
            print(get_current_time(), '二维码登录失败')
            return False
        else:
            print(get_current_time(), '二维码登录成功')
            self.nick_name = self.get_user_info()
            self._save_cookies()
            self.is_login = True
            return True

    def _get_reserve_url(self, sku_id):
        url = 'https://yushou.jd.com/youshouinfo.action'
        self.headers['Host'] = 'yushou.jd.com'
        self.headers['Referer'] = 'https://item.jd.com/{}.html'.format(sku_id)
        payload = {
            'callback': 'fetchJSON',
            'sku': sku_id
        }
        resp = self.sess.get(url=url, params=payload, headers=self.headers)
        js = parse_json(resp.text)
        # {"type":"1","hasAddress":false,"riskCheck":"0","flag":false,"num":941723,"stime":"2018-10-12 12:40:00","plusEtime":"","qiangEtime":"","showPromoPrice":"0","qiangStime":"","state":2,"sku":100000287121,"info":"\u9884\u7ea6\u8fdb\u884c\u4e2d","isJ":0,"address":"","d":48824,"hidePrice":"0","yueEtime":"2018-10-19 15:01:00","plusStime":"","isBefore":0,"url":"//yushou.jd.com/toYuyue.action?sku=100000287121&key=237af0174f1cffffd227a2f98481a338","etime":"2018-10-19 15:01:00","plusD":48824,"category":"4","plusType":0,"yueStime":"2018-10-12 12:40:00"};
        reserve_url = js.get('url')
        return 'https:' + reserve_url if reserve_url else None

    def make_reserve(self, sku_id):
        reserve_url = self._get_reserve_url(sku_id)
        if not reserve_url:
            print(get_current_time(), '{} 非预约商品'.format(sku_id))
            return
        self.headers['Host'] = 'yushou.jd.com'
        self.headers['Referer'] = 'https://item.jd.com/{}.html'.format(sku_id)
        resp = self.sess.get(url=reserve_url, headers=self.headers)
        soup = BeautifulSoup(resp.text, "html.parser")
        reserve_result = soup.find('p', {'class': 'bd-right-result'}).text.strip(' \t\r\n')
        # 预约成功，已获得抢购资格 / 您已成功预约过了，无需重复预约
        print(get_current_time(), reserve_result)

    def get_user_info(self):
        url = 'https://passport.jd.com/user/petName/getUserInfoForMiniJd.action'
        self.headers['Host'] = 'passport.jd.com'
        self.headers['Referer'] = 'https://www.jd.com/'
        payload = {
            'callback': 'jsonpUserinfo',
            '_': str(int(time.time() * 1000)),
        }
        try:
            resp = self.sess.get(url=url, params=payload, headers=self.headers)
            if not response_status(resp):
                print(get_current_time(), '获取用户信息失败')
                return ''
            js = parse_json(resp.text)
            # {'lastLoginTime': '', 'userLevel': 5, 'userScoreVO': {'default': False, 'financeScore': 101, 'consumptionScore': 12063, 'activityScore': 36, 'totalScore': 12431, 'accountScore': 31, 'pin': 'xxx', 'riskScore': 4}, 'imgUrl': '//storage.360buyimg.com/i.imageUpload/xxx.jpg', 'plusStatus': '0', 'realName': 'xxx', 'nickName': 'xxx'}
            # many user info are included in response, now return nick name in it
            return js.get('nickName')
        except Exception as e:
            print(get_current_time(), e)
            return ''

    def _get_item_detail_page(self, sku_id):
        url = 'https://item.jd.com/{}.html'.format(sku_id)
        self.headers['Host'] = 'item.jd.com'
        page = self.sess.get(url=url, headers=self.headers)
        return page

    def get_item_stock_state(self, sku_id='5089267', area='12_904_3375'):
        cat = self.item_cat.get(sku_id)
        if not cat:
            page = self._get_item_detail_page(sku_id)
            m = re.search(r'cat: \[(.*?)\]', page.text)
            cat = m.group(1)
            self.item_cat[sku_id] = cat

        url = 'https://c0.3.cn/stock'
        payload = {
            'skuId': sku_id,
            'buyNum': 1,
            'area': area,
            'ch': 1,
            '_': str(int(time.time() * 1000)),
            'callback': 'jQuery{}'.format(random.randint(1000000, 9999999)),
            'extraParam': '{"originid":"1"}',  # get error stock state without this param
            'cat': cat,  # get 403 Forbidden without this param (obtained from the detail page)
            # 'venderId': ''  # won't return seller information without this param (can be ignored)
        }
        self.headers['Host'] = 'c0.3.cn'
        self.headers['Referer'] = 'https://item.jd.com/{}.html'.format(sku_id)
        resp = requests.get(url=url, params=payload, headers=self.headers)

        js = parse_json(resp.text)
        stock_state = js['stock']['StockState']  # 33 -- 现货  34 -- 无货  40 -- 可配货
        stock_state_name = js['stock']['StockStateName']
        return stock_state, stock_state_name  # (33, '现货') (34, '无货') (36, '采购中') (40, '可配货')

    def if_item_in_stock(self, sku_id='5089267', area='12_904_3375'):
        return True if self.get_item_stock_state(sku_id, area)[0] == 33 else False

    def get_item_price(self, sku_id='5089267'):
        url = 'http://p.3.cn/prices/mgets'
        payload = {
            'type': 1,
            'pduid': int(time.time() * 1000),
            'skuIds': 'J_' + sku_id,
        }
        resp = self.sess.get(url=url, params=payload)
        js = parse_json(resp.text)
        return js['p']

    def add_item_to_cart(self, sku_id='862576', count=1):
        # if user add a item to shopping cart, it will be checked (or selected) by default
        # user can uncheck/check a item, which would make a post request to jd server to record
        # all checked items will be sent to checkout page
        # some items can't add to cart such as pre sale
        url = 'https://cart.jd.com/gate.action'
        payload = {
            'pid': sku_id,
            'pcount': count,
            'ptype': 1,
        }
        try:
            resp = self.sess.get(url=url, params=payload)
            soup = BeautifulSoup(resp.text, "html.parser")
            tag = soup.select('h3.ftx-02')  # [<h3 class="ftx-02">商品已成功加入购物车！</h3>]
            if not tag:
                print(get_current_time(), '{}添加到购物车失败'.format(sku_id))
                return False
            print(get_current_time(), '{}已成功加入购物车'.format(sku_id))
            return True
        except Exception as e:
            print(get_current_time(), e)
            return False

    def clear_cart(self):
        # 1.select all items  2.batch remove items
        select_url = 'https://cart.jd.com/selectAllItem.action'
        remove_url = 'https://cart.jd.com/batchRemoveSkusFromCart.action'
        data = {
            't': 0,
            'outSkus': '',
            'random': random.random(),
        }
        try:
            select_resp = self.sess.post(url=select_url, data=data)
            remove_resp = self.sess.post(url=remove_url, data=data)
            if (not response_status(select_resp)) or (not response_status(remove_resp)):
                print(get_current_time(), '购物车清空失败')
                return False
            print(get_current_time(), '购物车清空成功')
            return True
        except Exception as e:
            print(get_current_time(), e)
            return False

    def get_cart_detail(self):
        url = 'https://cart.jd.com/cart.action'
        cart_detail_format = '商品名称:{0}----单价:{1}----数量:{2}----总价:{3}'
        try:
            resp = self.sess.get(url)
            if not response_status(resp):
                print(get_current_time(), '获取购物车信息失败')
                return
            soup = BeautifulSoup(resp.text, "html.parser")

            print('************************购物车商品详情************************')
            for item in soup.select('div.item-form'):
                name = get_tag_value(item.select('div.p-name a'))
                price = get_tag_value(item.select('div.p-price strong'))
                quantity = get_tag_value(item.select('div.quantity-form input'), 'value')
                total_price = get_tag_value(item.select('div.p-sum strong'))
                print(cart_detail_format.format(name, price, quantity, total_price))
        except Exception as e:
            print(get_current_time(), e)

    def get_checkout_page_detail(self):
        url = 'http://trade.jd.com/shopping/order/getOrderInfo.action'
        # url = 'https://cart.jd.com/gotoOrder.action'
        payload = {
            'rid': str(int(time.time() * 1000)),
        }
        try:
            resp = self.sess.get(url=url, params=payload)
            if not response_status(resp):
                print(get_current_time(), '获取订单结算页信息失败')
                return
            soup = BeautifulSoup(resp.text, "html.parser")

            self.risk_control = get_tag_value(soup.select('input#riskControl'), 'value')

            print('************************订单结算页详情************************')
            items = soup.select('div.goods-list div.goods-items')[1:]
            checkout_item_detail = '商品名称:{0}----单价:{1}----数量:{2}----库存:{3}'
            for item in items:
                name = get_tag_value(item.select('div.p-name a'))
                div_tag = item.select('div.p-price')[0]
                price = get_tag_value(div_tag.select('strong.jd-price'))[2:]  # remove '￥ ' from the begin of price
                quantity = get_tag_value(div_tag.select('span.p-num'))[1:]  # remove 'x' from the begin of quantity
                state = get_tag_value(div_tag.select('span.p-state'))  # in stock or out of stock
                print(checkout_item_detail.format(name, price, quantity, state))

            sum_price = soup.find('span', id='sumPayPriceId').text[1:]  # remove '￥' from the begin of sum price
            address = soup.find('span', id='sendAddr').text[5:]  # remove '收件人:' from the begin of receiver
            receiver = soup.find('span', id='sendMobile').text[4:]  # remove '寄送至： ' from the begin of address
            print('应付总额:{0}'.format(sum_price))
            print('收货地址:{0}----收件人:{1}'.format(address, receiver))
        except Exception as e:
            print(get_current_time(), e)

    def submit_order(self):
        if not self.is_login:
            print(get_current_time(), '请先登录再提交订单！')
            return False

        url = 'https://trade.jd.com/shopping/order/submitOrder.action'
        # js function of submit order is included in https://trade.jd.com/shopping/misc/js/order.js?r=2018070403091
        data = {
            'overseaPurchaseCookies': '',
            'vendorRemarks': '[]',
            'submitOrderParam.sopNotPutInvoice': 'false',
            'submitOrderParam.trackID': 'TestTrackId',
            'submitOrderParam.ignorePriceChange': '0',
            'submitOrderParam.btSupport': '0',
            'submitOrderParam.jxj': 1,
            'riskControl': self.risk_control,
            'submitOrderParam.trackId': '9643cbd55bbbe103eef18a213e069eb0',  # Todo: need to get trackId
        }
        self.headers['Host'] = 'trade.jd.com'
        self.headers['Referer'] = 'http://trade.jd.com/shopping/order/getOrderInfo.action'

        try:
            resp = self.sess.post(url=url, data=data, headers=self.headers)
            if not response_status(resp):
                print(get_current_time(), '订单提交失败！')
                return False
            js = json.loads(resp.text)
            if js.get('success'):
                # {"message":null,"sign":null,"pin":"xxx","resultCode":0,"addressVO":null,"needCheckCode":false,"orderId": xxxx,"submitSkuNum":1,"deductMoneyFlag":0,"goJumpOrderCenter":false,"payInfo":null,"scaleSkuInfoListVO":null,"purchaseSkuInfoListVO":null,"noSupportHomeServiceSkuList":null,"success":true,"overSea":false,"orderXml":null,"cartXml":null,"noStockSkuIds":"","reqInfo":null,"hasJxj":false,"addedServiceList":null}
                order_id = js.get('orderId')
                item_num = js.get('submitSkuNum')
                print(get_current_time(), '订单提交成功! 订单号：{0}'.format(order_id))
                return True
            else:
                print(get_current_time(), '订单提交失败, 返回信息如下：')
                print(get_current_time(), js)
                return False
        except Exception as e:
            print(get_current_time(), e)
            return False

    def submit_order_by_time(self, buy_time, retry=2, interval=5):
        if not self.is_login:
            print(get_current_time(), '请先登录再定时下单！')
            return

        # '2018-09-28 22:45:50.000'
        buy_time = datetime.strptime(buy_time, "%Y-%m-%d %H:%M:%S.%f")
        print(get_current_time(), '正在等待下单……')

        now_time = datetime.now
        count = 1
        while True:
            if retry <= 0:
                break
            if now_time() >= buy_time:
                print(get_current_time(), '第%s次尝试下单……' % count)
                if self.submit_order():
                    break
                else:
                    retry -= 1
                    count += 1
                    time.sleep(interval)

    def submit_order_by_stock(self, sku_id='5089267', area='12_904_3375', interval=3):
        while True:
            if self.if_item_in_stock(sku_id=sku_id, area=area):
                print(get_current_time(), '%s有货了，正在提交订单……' % sku_id)
                self.submit_order()
                break
            else:
                print(get_current_time(), '%s无货，准备下一次查询……' % sku_id)
                time.sleep(interval)

    def get_order_info(self, unpaid=True):
        if not self.is_login:
            print(get_current_time(), '请先登录再查询订单！')
            return False

        url = 'https://order.jd.com/center/list.action'
        payload = {
            'search': 0,
            'd': 1,
            's': 4096,
        }  # Orders for nearly three months
        self.headers['Host'] = 'order.jd.com'
        self.headers['Referer'] = 'https://passport.jd.com/uc/login?ltype=logout'

        try:
            resp = self.sess.get(url=url, params=payload, headers=self.headers)
            if not response_status(resp):
                print(get_current_time(), '获取订单页信息失败')
                return
            soup = BeautifulSoup(resp.text, "html.parser")

            print('************************订单列表页查询************************')
            order_table = soup.find('table', {'class': 'order-tb'})
            table_bodies = order_table.select('tbody')
            exist_order = False
            for table_body in table_bodies:
                # check if order is waiting for payment
                wait_payment = bool(table_body.select('a.btn-pay'))

                # only show unpaid orders if unpaid=True
                if unpaid and (not wait_payment):
                    break

                exist_order = True

                # get deal_time, order_id
                tr_th = table_body.select('tr.tr-th')[0]
                deal_time = get_tag_value(tr_th.select('span.dealtime'))
                order_id = get_tag_value(tr_th.select('span.number a'))

                # get sum_price, pay_method
                amount_div = table_body.find('div', {'class': 'amount'})
                sum_price = ''
                pay_method = ''
                if amount_div:
                    spans = amount_div.select('span')
                    pay_method = get_tag_value(spans, index=1)
                    # if the order is waiting for payment, the price after the discount is shown.
                    if wait_payment:
                        sum_price = get_tag_value(amount_div.select('strong'), index=1)[1:]
                    else:
                        sum_price = get_tag_value(spans, index=0)[4:]

                # get order status
                order_status = get_tag_value(table_body.select('span.order-status'))

                # get name and quantity of items in order
                items_dict = dict()  # {'item_id_1': quantity_1, 'item_id_2': quantity_2, ...}
                tr_bds = table_body.select('tr.tr-bd')
                for tr_bd in tr_bds:
                    item = tr_bd.find('div', {'class': 'goods-item'})
                    if not item:
                        break
                    item_id = item.get('class')[1][2:]
                    quantity = get_tag_value(tr_bd.select('div.goods-number'))[1:]
                    items_dict[item_id] = quantity
                order_info_format = '订单号:{0}----下单时间:{1}----商品列表:{2}----订单状态:{3}----总金额:{4}元----付款方式:{5}'
                print(order_info_format.format(order_id, deal_time, parse_items_dict(items_dict), order_status, sum_price, pay_method))

            if not exist_order:
                print(get_current_time(), '订单查询为空')
        except Exception as e:
            print(get_current_time(), e)

    def _get_seckill_url(self, sku_id):
        """获取商品的抢购链接
        :param sku_id: 商品id
        :return: 商品的抢购链接
        """
        url = 'https://itemko.jd.com/itemShowBtn'
        self.headers['Host'] = 'itemko.jd.com'
        self.headers['Referer'] = 'https://item.jd.com/{}.html'.format(sku_id)
        payload = {
            'callback': 'jQuery{}'.format(random.randint(1000000, 9999999)),
            'skuId': sku_id,
            'from': 'pc',
            '_': str(int(time.time() * 1000)),
        }
        resp = self.sess.get(url=url, headers=self.headers, params=payload)
        js = parse_json(resp.text)

        # https://divide.jd.com/user_routing?skuId=8654289&sn=c3f4ececd8461f0e4d7267e96a91e0e0&from=pc
        router_url = 'https:' + js.get('url')

        # 点击"抢购"按钮后，会有两次302跳转，最后到达订单结算页面
        # 这里返回第一次跳转后的页面url，作为商品的抢购链接
        # https://marathon.jd.com/captcha.html?skuId=8654289&sn=c3f4ececd8461f0e4d7267e96a91e0e0&from=pc
        seckill_url = router_url.replace('divide', 'marathon').replace('user_routing', 'captcha.html')

        return seckill_url

    def request_seckill_url(self, sku_id):
        """访问商品的抢购链接（用于设置cookie等）
        :param sku_id: 商品id
        """
        self.seckill_url = self._get_seckill_url(sku_id) if not self.seckill_url else self.seckill_url
        self.headers['Host'] = 'marathon.jd.com'
        self.headers['Referer'] = 'https://item.jd.com/{}.html'.format(sku_id)
        self.sess.get(url=self.seckill_url, headers=self.headers, allow_redirects=False)

    def request_seckill_checkout_page(self, sku_id):
        """访问抢购订单结算页面
        :param sku_id: 商品id
        """
        url = 'https://marathon.jd.com/seckill/seckill.action'
        payload = {
            'skuId': sku_id,
            'num': 1,
            'rid': int(time.time())
        }
        self.headers['Host'] = 'marathon.jd.com'
        self.headers['Referer'] = 'https://item.jd.com/{}.html'.format(sku_id)
        resp = self.sess.get(url=url, params=payload, headers=self.headers)
        print(resp.text)

    def _get_default_address(self, sku_id):
        """获取用户默认下单地址
        :param sku_id: 商品id
        :return: 用户默认地址信息组成的dict
        """
        url = 'https://marathon.jd.com/async/getUsualAddressList.action'
        payload = {
            'skuId': sku_id,
            'yuyue': ''
        }
        self.headers['Host'] = 'marathon.jd.com'
        resp = self.sess.get(url=url, params=payload, headers=self.headers)

        # 常用地址列表，第一个为默认地址
        usual_addr_list = json.loads(resp.text)
        return usual_addr_list[0]

    def _gen_seckill_order_param(self, sku_id):
        """生成提交抢购订单所需的请求体参数
        :param sku_id: 商品id
        :return: 请求体参数组成的dict
        """

        # 获取用户默认下单地址
        self.default_addr = self._get_default_address(sku_id) if not self.default_addr else self.default_addr

        data = {
            'orderParam.name': self.default_addr.get('name'),
            'orderParam.addressDetail': self.default_addr.get('addressDetail'),
            'orderParam.mobile': self.default_addr.get('mobileWithXing'),
            'orderParam.email': '',
            'orderParam.provinceId': self.default_addr.get('provinceId'),
            'orderParam.cityId': self.default_addr.get('cityId'),
            'orderParam.countyId': self.default_addr.get('countyId'),
            'orderParam.townId': self.default_addr.get('townId'),
            'orderParam.paymentType': 4,
            'orderParam.password': '',
            'orderParam.invoiceTitle': 4,
            'orderParam.invoiceContent': 1,
            'orderParam.invoiceCompanyName': '',
            'orderParam.invoiceTaxpayerNO': '',
            'orderParam.invoiceEmail': '',
            'orderParam.invoicePhone': self.default_addr.get('mobileWithXing'),
            'orderParam.usualAddressId': self.default_addr.get('id'),
            'skuId': sku_id,
            'num': 1,
            'orderParam.provinceName': self.default_addr.get('provinceName'),
            'orderParam.cityName': self.default_addr.get('cityName'),
            'orderParam.countyName': self.default_addr.get('countyName'),
            'orderParam.townName': self.default_addr.get('townName'),
            'orderParam.codTimeType': 3,
            'orderParam.mobileKey': self.default_addr.get('mobileKey'),
            'eid': self.eid,
            'fp': self.fp,
            'addressMD5': self.default_addr.get('md5'),
            'yuyue': '',
            'yuyueAddress': 0,
        }

        return data

    def submit_seckill_order(self, sku_id):
        """提交抢购（秒杀）订单
        :param sku_id: 商品id
        :return: 抢购结果 True/False
        """
        url = 'https://marathon.jd.com/seckill/submitOrder.action'
        payload = {
            'skuId': sku_id,
            'vid': ''
        }
        self.seckill_data = self._gen_seckill_order_param(sku_id) if not self.seckill_data else self.seckill_data
        self.headers['Host'] = 'marathon.jd.com'
        self.headers['Referer'] = 'https://marathon.jd.com/seckill/seckill.action?skuId={0}&num=1&rid={1}'\
            .format(sku_id, int(time.time()))
        resp = self.sess.post(url=url, params=payload, data=self.seckill_data, headers=self.headers)

        # 抢购返回信息：
        # //marathon.jd.com/koFail.html?reason=
        # //sko.jd.com/success/success.action?orderId=81511218799&rid=0.1877352502777856
        message_url = resp.text
        if 'success' in message_url:
            order_id = dict(parse.parse_qsl(parse.urlsplit(message_url).query)).get('orderId')
            print(get_current_time(), '抢购成功，订单号：{}'.format(order_id))
            return True
        else:
            print(get_current_time(), '抢购失败，返回信息：{}'.format(parse.unquote(message_url)))
            return False

    def exec_seckill(self, sku_id, retry=4, interval=4):
        """执行抢购

        抢购商品的下单流程与普通商品不同，不支持加入购物车，主要执行流程如下：
        1. 访问商品的抢购链接
        2. 访问抢购订单结算页面（好像可以省略这步，待测试）
        3. 提交抢购（秒杀）订单

        :param sku_id: 商品id
        :param retry: 抢购重复执行次数，可选参数，默认3次
        :param interval: 抢购执行间隔，可选参数，默认4秒
        """

        for _ in range(retry):
            self.request_seckill_url(sku_id)
            self.request_seckill_checkout_page(sku_id)
            if self.submit_seckill_order(sku_id):
                break
            time.sleep(interval)

        print(get_current_time(), '抢购流程执行完毕！')
