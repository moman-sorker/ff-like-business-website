import aiohttp
import asyncio
import requests
from app.encryption import encrypt_message
from app.protobuf_handler import create_like_protobuf, decode_protobuf
from config import VERSION


def get_headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "X-Unity-Version": "2018.4.11f1",
        "X-GA": "v1 1",
        "ReleaseVersion": VERSION,
        "Content-Type": "application/x-www-form-urlencoded",
        # "Content-Length": "16",
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
        "Connection": "Keep-Alive",
        "Accept-Encoding": "gzip"
    }

async def send_request(encrypted_uid, token, url):
    try:
        edata = bytes.fromhex(encrypted_uid)
        headers = get_headers(token)

        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=edata, headers=headers) as response:
                text = await response.text()
                return {
                    "token": token,
                    "response": text,
                    "status": response.status
                }

    except Exception as e:
        print("ERROR send_request:", str(e))
        return {
            "token": token,
            "response": None,
            "status": "error"
        }


async def send_multiple_requests(uid, server_name, url, tokens):
    region = server_name
    protobuf_message = create_like_protobuf(uid, region)
    if protobuf_message is None:
        return None
    encrypted_uid = encrypt_message(protobuf_message)
    if encrypted_uid is None:
        return None

    tasks = []
    for token_doc in tokens:
        token = token_doc["token"]
        tasks.append(send_request(encrypted_uid, token, url))

    results = await asyncio.gather(*tasks, return_exceptions=True)
  
    return results


def make_request(encrypt, url, token):
    edata = bytes.fromhex(encrypt)
    headers = get_headers(token)
    try:
        response = requests.post(url, data=edata, headers=headers, verify=False)
        # print(response.status_code)
        return decode_protobuf(response.content)
    except Exception:
        return None
