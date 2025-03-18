import os
import sys
import time
import web3
import json
import random
import requests
import ua_generator
from datetime import datetime, timedelta
from eth_account.messages import encode_defunct
from web3 import Account
import asyncio

def log(msg):
    now = datetime.now().isoformat(" ").split(".")[0]
    print(f"[{now}] {msg}")

def validate_private_key_with_web3(private_key):
    if not isinstance(private_key, str):
        raise ValueError("Private key must be a string.")
    if not private_key.startswith("0x") or len(private_key) != 66:
        raise ValueError("Invalid private key: must be 64 hex characters prefixed with '0x'.")
    
    try:
        Account.from_key(private_key)
        return True
    except Exception as e:
        raise ValueError(f"Invalid private key: {e}")

def ensure_file_exists(filename):
    if not os.path.exists(filename):
        with open(filename, "w") as f:
            pass

async def http(ses: requests.Session, url, data=None):
    while True:
        try:
            if data is None:
                res = ses.get(url=url, timeout=10)
            elif data == "":
                res = ses.post(url=url, timeout=10)
            else:
                res = ses.post(url=url, data=data, timeout=10)
            
            if res.status_code in [502, 504, 500]:
                log(f"error : HTTP {res.status_code} encountered!")
                time.sleep(3)
                continue
            elif res.status_code >= 400:
                log(f"error : HTTP {res.status_code}!")
                return None

            if "<title>502 Bad Gateway</title>" in res.text or "<title>504 Gateway Time-out</title>" in res.text:
                log("error : Bad gateway or timeout in HTML content!")
                time.sleep(3)
                continue

            return res

        except (
            requests.exceptions.ConnectTimeout,
            requests.exceptions.ConnectionError,
            requests.exceptions.ReadTimeout,
            requests.exceptions.ProxyError,
            requests.exceptions.Timeout,
        ) as e:
            log(f"connection error: {e}")
            time.sleep(3)

class Start:
    def __init__(self, privatekey, proxy):
        validate_private_key_with_web3(privatekey)
        headers = {"user-agent": ua_generator.generate().text}
        proxy = {"http": proxy, "https": proxy}
        self.ses = requests.Session()
        self.ses.headers.update(headers)
        self.ses.proxies.update(proxy)
        self.wallet = web3.Account.from_key(private_key=privatekey)
        self.hostname = "layeredge.io"

    async def start(self):
        try:
            res = await http(ses=self.ses, url="https://ipv4.webshare.io")
            if res is None:
                return None
            log(f"Starting Node with ip: {res.text}")
            self.ses.headers.update(
                {
                    "host": f"referralapi.{self.hostname}",
                    "connection": "keep-alive",
                    "sec-ch-ua-platform": '"Windows"',
                    "accept": "application/json, text/plain, */*",
                    "content-type": "application/json",
                    "sec-ch-ua-mobile": "?0",
                    "origin": f"https://dashboard.{self.hostname}",
                    "sec-fetch-site": "same-site",
                    "sec-fetch-mode": "cors",
                    "sec-fetch-dest": "empty",
                    "referer": f"https://dashboard.{self.hostname}/",
                    "accept-language": "en-US,en;q=0.9",
                }
            )
            log(f"wallet addr : {self.wallet.address}")
            wallet_detail_url = f"https://referralapi.layeredge.io/api/referral/wallet-details/{self.wallet.address}"
            node_status_url = f"https://referralapi.{self.hostname}/api/light-node/node-status/{self.wallet.address}"
            daily_claim_url = (
                f"https://referralapi.{self.hostname}/api/light-node/claim-node-points"
            )
            res = await http(ses=self.ses, url=wallet_detail_url)
            ref_code = res.json().get("data", {}).get("referralCode")
            point = res.json().get("data", {}).get("nodePoints")
            last_claim = res.json().get("data", {}).get("lastClaimed")
            if last_claim is None:
                last_claim = (datetime.now() - timedelta(days=1)).isoformat()
            last_claim_day = last_claim.split("T")[0]
            log(f"referral code : {ref_code}")
            log(f"node point : {point}")
            now = datetime.now()
            message_claim = f"I am claiming my daily node point for {self.wallet.address} at {int(now.timestamp() * 1000)}"
            daily_claim_data = {
                "walletAddress": self.wallet.address,
                "timestamp": int(now.timestamp() * 1000),
                "sign": "",
            }
            if last_claim_day != now.isoformat().split("T")[0]:
                enmessage = encode_defunct(text=message_claim)
                sign = web3.Account.sign_message(enmessage, private_key=self.wallet.key)
                signature = f"0x{sign.signature.hex()}"
                daily_claim_data["sign"] = signature
                res = await http(
                    ses=self.ses, url=daily_claim_url, data=json.dumps(daily_claim_data)
                )
                if res.json().get("message") == "node points claimed successfully":
                    log(f"Successfully claimed daily point!")
                else:
                    log(f"failed to claim daily point!")
            
            while True:
                res = await http(ses=self.ses, url=node_status_url)
                if res is None:
                    return None
                start_time = res.json().get("data", {}).get("startTimestamp")
                if start_time is None:
                    start_url = f"https://referralapi.{self.hostname}/api/light-node/node-action/{self.wallet.address}/start"
                    timet = int(datetime.now().timestamp() * 1000)
                    message = f"Node activation request for {self.wallet.address} at {timet}"
                    enmessage = encode_defunct(text=message)
                    sign = web3.Account.sign_message(enmessage, private_key=self.wallet.key)
                    signature = f"0x{sign.signature.hex()}"
                    data = {
                        "sign": signature,
                        "timestamp": timet,
                    }
                    res = await http(ses=self.ses, url=start_url, data=json.dumps(data))
                    if res is None:
                        return None
                    if "node action executed successfully" not in res.json().get("message", ""):
                        log("Failed to Start Node!")
                        return None
                    log("Successfully Started Node!")
                
                    res = await http(ses=self.ses, url=wallet_detail_url)
                    if res is None:
                        log("Failed to retrieve wallet details after starting node.")
                    else:
                        point = res.json().get("data", {}).get("nodePoints")
                        if point is None:
                            log("Node points not provided in the wallet details response.")
                        else:
                            log(f"Updated Node Points: {point}")
                else:
                    log("Node already started!")

                random_sleep = random.randint(3600, 21600)
                
                log(f"Sleeping for {random_sleep} seconds...")
                await asyncio.sleep(random_sleep)
                
                log("Stopping the Node...")
                stop_url = f"https://referralapi.{self.hostname}/api/light-node/node-action/{self.wallet.address}/stop"
                timet = int(datetime.now().timestamp() * 1000)
                message = f"Node deactivation request for {self.wallet.address} at {timet}"
                enmessage = encode_defunct(text=message)
                sign = web3.Account.sign_message(enmessage, private_key=self.wallet.key)
                signature = f"0x{sign.signature.hex()}"
                data = {
                    "sign": signature,
                    "timestamp": timet,
                }

                retries = 0
                max_retries = 50

                while retries < max_retries:
                    res = await http(ses=self.ses, url=stop_url, data=json.dumps(data))
                    if res is None:
                        retries += 1
                        log(f"Failed to Stop Node (retry {retries}/{max_retries})")
                        await asyncio.sleep(2)
                        continue

                    if "Node action executed successfully" in res.json().get("message"):
                        log("Successfully stopped node!")
                        break 
                    else:
                        retries += 1
                        log(f"Failed to stop Node, HTTP response: {res.text} (retry {retries}/{max_retries})")
                        await asyncio.sleep(2) 
                        
                if retries == max_retries:
                    log(f"Failed to stop the Node after {max_retries} retries.")
                
                random_sleep = random.randint(11, 18)
                log(f"Sleeping for {random_sleep} seconds before restarting...")
                await asyncio.sleep(random_sleep)

        except Exception as e:
            log(f"error : {e}")
            return None

def get_proxy(index, proxies):
    if not proxies: 
        return None
    return proxies[index % len(proxies)]

async def process_private_key(privatekey, proxy, proxies, key_index, total_keys, max_retries=5):
    retries = 0
    while retries < max_retries:
        log(f"Processing private key {key_index + 1}/{total_keys} with proxy {proxy or 'None'}...")
        try:
            st = await Start(proxy=proxy, privatekey=privatekey).start()
            if st is not None:
                log(f"Successfully completed actions for private key {key_index + 1}/{total_keys}.")
                return True
            retries += 1
            log(f"Retrying private key {key_index + 1}/{total_keys} (Attempt {retries}/{max_retries})...")
            proxy = get_proxy(random.randint(0, total_keys - 1), proxies) if proxies else None
        except Exception as e:
            log(f"Error processing private key {key_index + 1}: {e}")
            retries += 1

    log(f"Skipping private key {key_index + 1}/{total_keys} after {max_retries} failed attempts.")
    return False

async def main():
    os.system("cls" if os.name == "nt" else "clear")
    print(
     """
     
     ▒█░░░ █▀▀█ █░░█ █▀▀ █▀▀█ ▒█▀▀▀ █▀▀▄ █▀▀▀ █▀▀ ▒█▀▀█ █▀▀█ █▀▀█ █▀▀█ 
     ▒█░░░ █▄▄█ █▄▄█ █▀▀ █▄▄▀ ▒█▀▀▀ █░░█ █░▀█ █▀▀ ▒█░░░ █▄▄▀ █▄▄█ █░░█ 
     ▒█▄▄█ ▀░░▀ ▄▄▄█ ▀▀▀ ▀░▀▀ ▒█▄▄▄ ▀▀▀░ ▀▀▀▀ ▀▀▀ ▒█▄▄█ ▀░▀▀ ▀░░▀ █▀▀▀
     """
    )

    print()
    ensure_file_exists("privatekeys.txt")
    ensure_file_exists("proxies.txt")
    privatekeys = open("privatekeys.txt").read().splitlines()
    proxies = open("proxies.txt").read().splitlines()

    print(f"Number of private key(s) : {len(privatekeys)}")
    print(f"Number of Proixies : {len(proxies)}")
    print()

    tasks = []
    for i, privatekey in enumerate(privatekeys):
        proxy = get_proxy(i, proxies)
        tasks.append(process_private_key(privatekey, proxy, proxies, i, len(privatekeys)))

    await asyncio.gather(*tasks)

    print("~" * 50)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit()
