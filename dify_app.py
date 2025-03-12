import requests


def main(input_json: str, header: str) -> dict:
    header = eval(header)
    response = requests.get(input_json, headers=header, timeout=10).json()
    start = response['start']
    link_suffix = response[start]['loadFile_bloblink_']
    return {"result": 'https://www.bydglobal.com' + link_suffix}
