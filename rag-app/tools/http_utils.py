"""
@Project ：start-map
@File    ：http_utils.py
@IDE     ：PyCharm
@Author  ：XMAN
@Date    ：2025/4/23 上午10:37
"""
import requests


class RequestHandler:
    def __init__(self, base_url: str, log=None, timeout: int = 10, max_retries: int = 3):
        self.base_url = base_url
        self.timeout = timeout  # 超时时间
        self.max_retries = max_retries  # 重试次数
        self.logger = log

    def safe_send_request(self, resource: str, method: str, body=None, headers=None, files=None, json=None):
        """
        发送请求 附带重试机制
        :param resource: 请求资源
        :param method: 请求方式
        :param body: 请求数据
        :param headers: 请求报头
        :param files: 上传文件
        :return:
        """
        retries = 0
        response = None
        method = method.upper()
        url = self.base_url + resource
        headers = headers or {'content_type': "application/json"}
        while retries < self.max_retries:
            try:
                if method == 'GET':
                    response = requests.get(url, params=body, headers=headers)
                elif method == 'POST':
                    response = requests.post(url, data=body, headers=headers, files=files, json=json)
                elif method == 'PUT':
                    response = requests.put(url, data=body, headers=headers)
                elif method == 'DELETE':
                    response = requests.delete(url, data=body, headers=headers)

                if response.status_code != 200:
                    self.logger.error(f'Request failed with status code {response.status_code}')
                    response.raise_for_status()

                return self.parse_response(response)
            except Exception as e:
                print(e)
                self.logger.error('Request has something wrong:', e)
                retries += 1

    def parse_response(self, response):
        """ 解析响应返回数据 """
        try:
            return response.json()
        except Exception as e:
            self.logger.error("Failed to parse json response:", e)
            return response.text()


def generate_response(code, data=None):
    """ 生成响应 """
    _code_response = {
        200: HTTP_200_OK,
        400: HTTP_400_BAD_REQUEST,
        404: HTTP_404_NOT_FOUND,
        500: HTTP_500_SERVER_ERROR
    }
    if code not in _code_response:
        code = 200
    request_tuple = _code_response[code]

    if not isinstance(request_tuple, tuple):
        request_tuple = tuple(request_tuple)

    code, message = request_tuple
    return {
        'code': code,
        'message': message,
        'data': data
    }


HTTP_200_OK = 200, '请求成功'
HTTP_400_BAD_REQUEST = 400, '异常请求'
HTTP_404_NOT_FOUND = 404, '未找到请求资源'
HTTP_500_SERVER_ERROR = 500, '服务器数据异常'
