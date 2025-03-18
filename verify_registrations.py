import asyncio
import aiohttp
import json
import os
from web3 import Web3

BASE_URL = 'https://referralapi.layeredge.io/api/referral/register-wallet/tUCYwDDd'

def get_wallet_addresses(file_path='pending_keys.txt'):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"{file_path} not found.")
    
    wallet_addresses = []
    with open(file_path, 'r') as file:
        for line in file:
            private_key = line.strip()
            if private_key:
                try:
                    wallet_address = Web3().eth.account.from_key(private_key).address
                    wallet_addresses.append((private_key, wallet_address))
                except Exception as e:
                    print(f"Error processing private key: {private_key[:5]}... - {e}")
    return wallet_addresses

def move_private_key(private_key, source_file='pending_keys.txt', target_file='privatekeys.txt'):
    with open(source_file, 'r') as file:
        lines = file.readlines()
    
    with open(source_file, 'w') as file:
        file.writelines(line for line in lines if line.strip() != private_key)
    
    with open(target_file, 'a') as file:
        file.write(private_key + '\n')

async def register_wallet(session, private_key, wallet_address, max_retries=3):
    url = BASE_URL
    payload = {"walletAddress": wallet_address}
    headers = {
        'accept': 'application/json, text/plain, */*',
        'content-type': 'application/json',
        'origin': 'https://dashboard.layeredge.io',
        'referer': 'https://dashboard.layeredge.io/',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 Edg/132.0.0.0',
    }

    for attempt in range(max_retries):
        try:
            async with session.post(url, headers=headers, data=json.dumps(payload)) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"[SUCCESS] Wallet: {wallet_address} - {data['message']}")
                    move_private_key(private_key)
                    return data
                elif response.status == 409:
                    data = await response.json()
                    print(f"[INFO] Wallet: {wallet_address} - {data['message']}")
                    return data
                else:
                    print(f"[RETRY {attempt + 1}] Wallet: {wallet_address} - Status: {response.status}")
        except Exception as e:
            print(f"[ERROR] Wallet: {wallet_address} - Attempt {attempt + 1} failed: {e}")
        await asyncio.sleep(2)
    print(f"[FAILED] Wallet: {wallet_address} - Max retries reached.")
    return None

async def main():
    wallet_addresses = get_wallet_addresses()
    if not wallet_addresses:
        print("No valid wallet addresses found.")
        return

    async with aiohttp.ClientSession() as session:
        tasks = [register_wallet(session, private_key, wallet) for private_key, wallet in wallet_addresses]
        await asyncio.gather(*tasks)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Unexpected error: {e}")
