import os
import sys
import web3
import json
import random
import ua_generator
from datetime import datetime, timedelta
from eth_account.messages import encode_defunct
from web3 import Account
import asyncio
import aiohttp
import uuid
import re
from faker import Faker


DO_PROOF = False # Set to True to submit proof, False to skip. - cus y'all must have done it by now.
DO_TWITTER = True # Set to True to connect Twitter, False to skip.
SHORT_SLEEP = True # Set to True to sleep to 1-2 mins. before restarting, False to sleep 1-6 hours.

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


class Start:
    def __init__(self, privatekey, proxy):
        validate_private_key_with_web3(privatekey)
        self.headers = {"user-agent": ua_generator.generate().text}
        self.proxy = proxy
        self.wallet = web3.Account.from_key(private_key=privatekey)
        self.hostname = "layeredge.io"

    async def http(self, session, url, data=None, method="GET"):
        try:
            request_kwargs = {
                "method": method,
                "url": url,
                "timeout": aiohttp.ClientTimeout(total=10),
            }
            if self.proxy:
                request_kwargs["proxy"] = self.proxy
            if data and method in {"POST", "PUT", "PATCH"}: 
                request_kwargs["json"] = data

            async with session.request(**request_kwargs) as response:
                content_type = response.headers.get("Content-Type", "")
                body = await response.text() 

                if response.status >= 400:
                    try:
                        error_data = json.loads(body)
                        if "message" in error_data:
                            log(f"Error {response.status}: {error_data['message']}")
                            return error_data 
                    except json.JSONDecodeError:
                        if "<title>" in body:
                            if "<title>502 Bad Gateway</title>" in body or "<title>504 Gateway Time-out</title>" in body:
                                log(f"Error {response.status}: Bad gateway or timeout detected.")
                            else:
                                log(f"Error {response.status}: HTML error detected.")
                        else:
                            log(f"Error {response.status}: {body}")
                        return None

                if "application/json" in content_type:
                    return await response.json()
                return body

        except aiohttp.ClientError as e:
            log(f"HTTP request failed: {e}")
            return None
        except Exception as e:
            log(f"Unexpected error: {e}")
            return None

    async def claim_proof_points(self, session):
        url = "https://referralapi.layeredge.io/api/task/proof-submission"
        max_attempts = 5
        attempt = 1
        now = datetime.now()
        message_claim = f"I am claiming my proof submission node points for {self.wallet.address} at {int(now.timestamp() * 1000)}"
        enmessage = encode_defunct(text=message_claim)
        sign = web3.Account.sign_message(enmessage, private_key=self.wallet.key)
        signature = f"0x{sign.signature.hex()}"

        payload = {
                        "walletAddress": self.wallet.address,
                        "timestamp": int(now.timestamp() * 1000),
                        "sign": signature
                    }

        while attempt <= max_attempts:
            response = await self.http(
                            session, url=url, data=payload, method="POST"
                        )

            if response is None:
                log(f"Request failed on attempt {attempt}/{max_attempts}. Retrying...")
                if attempt == max_attempts:
                    log("Max retries reached. Giving up.")
                    return False
                await asyncio.sleep(1)
                attempt += 1
                continue

            if isinstance(response, dict) and response.get("message") == "proof submission task completed successfully":
                log("Success: Proof submission task completed successfully")
                return True

            if isinstance(response, dict) and response.get("statusCode") == 409 and response.get("message") == "proof submission task is already completed":
                log("Proof submission task has already been completed")
                return False

            log(f"Unexpected response on attempt {attempt}/{max_attempts}: {response}")
            if attempt == max_attempts:
                log("Max retries reached with unexpected responses. Giving up.")
                return False
            await asyncio.sleep(1)
            attempt += 1     


    async def claim_nodetask_points(self, session):
        url = "https://referralapi.layeredge.io/api/task/node-points"
        max_attempts = 5
        attempt = 1
        now = datetime.now()
        message_claim = f"I am claiming my light node run task node points for {self.wallet.address} at {int(now.timestamp() * 1000)}"
        enmessage = encode_defunct(text=message_claim)
        sign = web3.Account.sign_message(enmessage, private_key=self.wallet.key)
        signature = f"0x{sign.signature.hex()}"

        payload = {
                        "walletAddress": self.wallet.address,
                        "timestamp": int(now.timestamp() * 1000),
                        "sign": signature
                    }

        while attempt <= max_attempts:
            response = await self.http(
                            session, url=url, data=payload, method="POST"
                        )

            if response is None:
                log(f"Request failed on attempt {attempt}/{max_attempts}. Retrying...")
                if attempt == max_attempts:
                    log("Max retries reached. Giving up.")
                    return False
                await asyncio.sleep(1)
                attempt += 1
                continue

            if isinstance(response, dict) and response.get("message") == "node points task completed successfully":
                log("Success: Node task completed successfully")
                return True

            if isinstance(response, dict) and response.get("statusCode") == 409 and response.get("message") == "node run task is already completed":
                log("Node task has already been completed")
                return False

            log(f"Unexpected response on attempt {attempt}/{max_attempts}: {response}")
            if attempt == max_attempts:
                log("Max retries reached with unexpected responses. Giving up.")
                return False
            await asyncio.sleep(1)
            attempt += 1              
    
    def gen_twitter_username(self):
        fake = Faker()
        base_username = fake.user_name()
        unique_suffix = str(uuid.uuid4().hex)[:4]
        username = f"{base_username}{unique_suffix}"
        username = re.sub(r'[^a-zA-Z0-9_]', '', username)
        if len(username) > 15:
            username = username[:15]
        elif len(username) < 4:
            username = f"{username}{fake.random_number(digits=4-len(username))}"
        return username


    async def connect_twitter(self, session, max_attempts=5):
        url = "https://referralapi.layeredge.io/api/task/connect-twitter" 
        attempt = 1
        now = datetime.now()
        message_claim = f"I am verifying my Twitter authentication for {self.wallet.address} at {int(now.timestamp() * 1000)}"
        enmessage = encode_defunct(text=message_claim)
        sign = web3.Account.sign_message(enmessage, private_key=self.wallet.key)
        signature = f"0x{sign.signature.hex()}"
        twitter_id =  self.gen_twitter_username()
    
        payload = {
            "walletAddress": self.wallet.address,
            "timestamp": int(now.timestamp() * 1000),
            "sign": signature,
            "twitterId": twitter_id
        }
    
        while attempt <= max_attempts:
            response = await self.http(
                session, url=url, data=payload, method="POST"
            )
    
            if response is None:
                log(f"Request failed on attempt {attempt}/{max_attempts}. Retrying...")
                if attempt == max_attempts:
                    log("Max retries reached. Giving up.")
                    return False
                await asyncio.sleep(1)
                attempt += 1
                continue
    
            if isinstance(response, dict) and response.get("message") == "Twitter authentication verified":
                if response.get("data", {}).get("isFirstTimeTwitterAuth", True):
                    log("Success: Twitter connect task completed successfully!")
                    return True
                else:
                    log("Twitter connect task has already been completed (not first-time auth)")
                    return False
                
            if isinstance(response, dict) and response.get("message") == "Your wallet is already linked with a different Twitter account":
                 log("Twitter connect task has already been completed")
                 return True
            
            log(f"Unexpected response on attempt {attempt}/{max_attempts}: {response}")
            if attempt == max_attempts:
                log("Max retries reached with unexpected responses. Giving up.")
                return False
            await asyncio.sleep(1)
            attempt += 1
    
        return False        


    async def start(self):
        async with aiohttp.ClientSession(headers=self.headers) as session:
            try:
                session.headers.update(
                    {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
                        "Accept": "application/json, text/plain, */*",
                        "Referer": "https://dashboard.layeredge.io/",
                        "Origin": "https://dashboard.layeredge.io",
                        "Connection": "keep-alive",
                    }
                )

                # Fetch wallet details
                wallet_detail_url = f"https://referralapi.layeredge.io/api/referral/wallet-details/{self.wallet.address}"
                wallet_details = await self.http(session, url=wallet_detail_url)
                if not wallet_details:
                    log("Failed to fetch wallet details")
                    return None

                ref_code = wallet_details.get("data", {}).get("referralCode")
                points = wallet_details.get("data", {}).get("nodePoints")
                last_claim = wallet_details.get("data", {}).get("lastClaimed")

                if not last_claim:
                    last_claim = (datetime.now() - timedelta(days=1)).isoformat()
                last_claim_day = last_claim.split("T")[0]

                log(f"Referral code: {ref_code}")
                log(f"Node points: {points}")

                now = datetime.now()


                # Daily Claim
                daily_claim_url = f"https://referralapi.{self.hostname}/api/light-node/claim-node-points"
                if last_claim_day != now.isoformat().split("T")[0]:
                    message_claim = f"I am claiming my daily node point for {self.wallet.address} at {int(now.timestamp() * 1000)}"
                    enmessage = encode_defunct(text=message_claim)
                    sign = web3.Account.sign_message(enmessage, private_key=self.wallet.key)
                    signature = f"0x{sign.signature.hex()}"

                    daily_claim_data = {
                        "walletAddress": self.wallet.address,
                        "timestamp": int(now.timestamp() * 1000),
                        "sign": signature,
                    }
                    claim_res = await self.http(
                        session, url=daily_claim_url, data=daily_claim_data, method="POST"
                    )
                    if claim_res and claim_res.get("message") == "node points claimed successfully":
                        log("Successfully claimed daily point!")
                    else:
                        log("Failed to claim daily point!")


                # check and submit proof
                if DO_PROOF:
                   check_proof_claim_url = f"https://dashboard.layeredge.io/api/proofs/status?address={self.wallet.address}"
                   try:
                       check_proof_res = await self.http(
                           session, url=check_proof_claim_url, method="GET"
                       )
                       if check_proof_res and check_proof_res.get("hasSubmitted") is False:
   
                           submit_proof_url = "https://dashboard.layeredge.io/api/send-proof"
                           fake = Faker()
                           max_attempts = 5
                           attempt = 1
   
                           while attempt <= max_attempts:
                               current_time = datetime.utcnow()
                               formatted_time = current_time.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
                               proof_message = f"I am submitting a proof for LayerEdge at {formatted_time}"
   
                               enmessage = encode_defunct(text=proof_message)
                               sign = web3.Account.sign_message(enmessage, private_key=self.wallet.key)
                               signature = f"0x{sign.signature.hex()}"
   
                               proof_data = {
                                   "address": self.wallet.address,
                                   "message": proof_message,
                                   "proof": fake.sentence(nb_words=8),
                                   "signature": signature, 
                               }
   
                               proof_res = await self.http(session, url=submit_proof_url, data=proof_data, method="POST"
                               )
   
                               if proof_res is None:
                                   log(f"Request failed on attempt {attempt}/{max_attempts}. Retrying...")
                                   if attempt == max_attempts:
                                       log("Max retries reached. Giving up.")
                                       return False
                                   await asyncio.sleep(1) 
                                   attempt += 1
                                   continue
   
                               if isinstance(proof_res, dict) and proof_res.get("success") is True:
                                   log(f"Success: {proof_res.get('message')}")
                                   await self.claim_proof_points(session)
                                   await self.claim_nodetask_points(session)
   
                               if isinstance(proof_res, dict) and proof_res.get("error") and "Proof already submitted" in proof_res.get("error"):
                                   log(f"Proof already submitted: {proof_res.get('previousSubmission')}")
                                   return False
   
                               log(f"Unexpected response on attempt {attempt}/{max_attempts}: {proof_res}")
                               if attempt == max_attempts:
                                   log("Max retries reached with unexpected responses. Giving up.")
                                   return False
                               await asyncio.sleep(1)
                               attempt += 1
   
                       elif check_proof_res and check_proof_res.get("hasSubmitted") is True:
                           print("Proof has already been submitted.")
                           await self.claim_proof_points(session)
                           await self.claim_nodetask_points(session)
   
                       else:
                           print("Proof has been submitted or response is invalid.")
                   except Exception as e:
                       print(f"Error during HTTP request: {e}")


                # Connect Twitter
                if DO_TWITTER:
                   await self.connect_twitter(session)

                # Start the node
                while True:
                    try:
                        node_status_url = f"https://referralapi.{self.hostname}/api/light-node/node-status/{self.wallet.address}"
                        retries = 0
                        max_retries = 6  # Number of retries
                        retry_delay = 2  # Delay between retries (in seconds)

                        while retries < max_retries:
                            node_status = await self.http(session, url=node_status_url)

                            if node_status:
                                break
                            else:
                                retries += 1
                                log(f"Failed to fetch node status. Retrying {retries}/{max_retries}...")
                                await asyncio.sleep(retry_delay)  # Wait before retrying

                        if retries == max_retries:
                            log("Failed to fetch node status after maximum retries.")
                            return None

                        start_time = node_status.get("data", {}).get("startTimestamp")
                        if not start_time:
                            start_url = f"https://referralapi.{self.hostname}/api/light-node/node-action/{self.wallet.address}/start"
                            timet = int(datetime.now().timestamp() * 1000)
                            message = f"Node activation request for {self.wallet.address} at {timet}"
                            enmessage = encode_defunct(text=message)
                            sign = web3.Account.sign_message(enmessage, private_key=self.wallet.key)
                            signature = f"0x{sign.signature.hex()}"

                            start_data = {"sign": signature, "timestamp": timet}
                            start_res = await self.http(
                                 session, url=start_url, data=start_data, method="POST"
                             )
                            if start_res and "node action executed successfully" in start_res.get("message", ""):
                                log("Successfully started node!")
                            else:
                                log("Failed to start node!")
                                return None

                        random_sleep = random.randint(3600, 21600) if not SHORT_SLEEP else random.randint(60, 120)
                        await asyncio.sleep(random_sleep)

                        # stopping the node
                        #  stop_url = f"https://referralapi.{self.hostname}/api/light-node/node-action/{self.wallet.address}/stop"
                        #  timet = int(datetime.now().timestamp() * 1000)
                        #  message = f"Node deactivation request for {self.wallet.address} at {timet}"
                        #  enmessage = encode_defunct(text=message)
                        #  sign = web3.Account.sign_message(enmessage, private_key=self.wallet.key)
                        #  signature = f"0x{sign.signature.hex()}"

                        #  stop_data = {"sign": signature, "timestamp": timet}
                        #  retries = 0
                        #  max_retries = 6
                        #  retrying = True

                        #  while retries < max_retries and retrying:
                        #        stop_res = await self.http(
                        #            session, url=stop_url, data=stop_data, method="POST"
                        #        )

                        #        if stop_res:
                        #            message = stop_res.get("message", "")
                        #            if message == "no node running for given address":
                        #                log("No node is running for the given address. Exiting retries.")
                        #                retrying = False  # Prevent further retries
                        #                break  # Exit the retry loop

                        #            if "node action executed successfully" in message:
                        #                log("Node stopped successfully.")
                        #                retrying = False  # Prevent further retries
                        #                break  # Exit the retry loop

                        #        # If no break occurred, increment retries and retry
                        #        retries += 1
                        #        log(f"Retrying to stop node... Attempt {retries}/{max_retries}")
                        #        await asyncio.sleep(2)

                        #  if retries == max_retries:
                        #      log("Failed to stop the node after maximum retries.")

                        log(f"Sleeping before restarting the node...")
                        await asyncio.sleep(random.randint(1, 2))
                    except Exception as e:
                        log(f"Unexpected error in the main loop: {e}")
                        break
            except Exception as e:
                log(f"Error in start: {e}")
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
