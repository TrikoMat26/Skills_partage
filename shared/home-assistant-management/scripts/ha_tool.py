#!/usr/bin/env python3
import argparse
import json
import os
import sys
import urllib.request
import urllib.error
import time

try:
    import websocket
except ImportError:
    print("Error: websocket-client package is required. Install it using 'pip install websocket-client'.", file=sys.stderr)
    sys.exit(1)

def find_env_file():
    # Check current directory, parent directory, and script directories
    paths_to_check = [
        os.path.join(os.getcwd(), ".env"),
        os.path.join(os.path.dirname(os.getcwd()), ".env"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"),
    ]
    for p in paths_to_check:
        if os.path.exists(p):
            return p
    return None

def load_env():
    env_vars = {}
    env_path = find_env_file()
    if env_path:
        print(f"Loading environment from: {env_path}", file=sys.stderr)
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    env_vars[k.strip()] = v.strip()
    else:
        print("Warning: No .env file found. Looking in system environment variables.", file=sys.stderr)
    return env_vars

def get_ha_client(env_vars):
    token = env_vars.get("HOMEASSISTANT_TOKEN") or os.environ.get("HOMEASSISTANT_TOKEN")
    if not token:
        print("Error: HOMEASSISTANT_TOKEN not found in .env or environment.", file=sys.stderr)
        sys.exit(1)
        
    local_url = env_vars.get("HOMEASSISTANT_URL_LOCAL") or os.environ.get("HOMEASSISTANT_URL_LOCAL") or "http://192.168.1.79:8123"
    external_url = env_vars.get("HOMEASSISTANT_URL_EXTERNAL") or os.environ.get("HOMEASSISTANT_URL_EXTERNAL") or "https://triko26.duckdns.org"
    
    # Clean trailing slashes
    local_url = local_url.rstrip("/")
    external_url = external_url.rstrip("/")
    
    # Try local first
    print(f"Connecting to local URL: {local_url}...", file=sys.stderr)
    try:
        req = urllib.request.Request(
            f"{local_url}/api/",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=3) as r:
            if r.status == 200:
                print("Connection to local Home Assistant succeeded.", file=sys.stderr)
                return local_url, token
    except Exception as e:
        print(f"Local URL connection failed: {e}. Trying external URL...", file=sys.stderr)
        
    # Try external
    print(f"Connecting to external URL: {external_url}...", file=sys.stderr)
    try:
        req = urllib.request.Request(
            f"{external_url}/api/",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            if r.status == 200:
                print("Connection to external Home Assistant succeeded.", file=sys.stderr)
                return external_url, token
    except Exception as e:
        print(f"External URL connection failed: {e}.", file=sys.stderr)
        
    print("Error: Could not connect to Home Assistant via local or external URL.", file=sys.stderr)
    sys.exit(1)

def get_ws_url(http_url):
    if http_url.startswith("https://"):
        return http_url.replace("https://", "wss://") + "/api/websocket"
    else:
        return http_url.replace("http://", "ws://") + "/api/websocket"

def make_api_request(url, token, endpoint, method="GET", data=None):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    req_url = f"{url}/api/{endpoint}"
    req_data = json.dumps(data).encode("utf-8") if data is not None else None
    
    req = urllib.request.Request(req_url, headers=headers, method=method, data=req_data)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        print(f"HTTP Error {e.code}: {e.reason}\nBody: {body}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Network error: {e}", file=sys.stderr)
        sys.exit(1)

def get_url_path(dashboard_key):
    if dashboard_key in ["lovelace", "lovelace.lovelace"]:
        return None
    if dashboard_key.startswith("lovelace."):
        return dashboard_key.replace("lovelace.", "", 1)
    return dashboard_key

def download_dashboard_ws(http_url, token, dashboard_key):
    ws_url = get_ws_url(http_url)
    print(f"Connecting to WebSocket: {ws_url}...", file=sys.stderr)
    try:
        ws = websocket.create_connection(ws_url)
        msg = json.loads(ws.recv())
        if msg.get("type") == "auth_required":
            ws.send(json.dumps({
                "type": "auth",
                "access_token": token
            }))
            auth_resp = json.loads(ws.recv())
            if auth_resp.get("type") != "auth_ok":
                print("WebSocket Authentication failed.", file=sys.stderr)
                ws.close()
                sys.exit(1)
            
            # Send get config command
            cmd = {
                "id": 1,
                "type": "lovelace/config"
            }
            url_path = get_url_path(dashboard_key)
            if url_path:
                cmd["url_path"] = url_path
                
            ws.send(json.dumps(cmd))
            result = json.loads(ws.recv())
            ws.close()
            if result.get("success"):
                return result.get("result")
            else:
                print(f"WebSocket Get config failed: {result.get('error')}", file=sys.stderr)
                sys.exit(1)
        else:
            print(f"Unexpected handshake: {msg}", file=sys.stderr)
            ws.close()
            sys.exit(1)
    except Exception as e:
        print(f"WebSocket connection error: {e}", file=sys.stderr)
        sys.exit(1)

def upload_dashboard_ws(http_url, token, dashboard_key, config_data):
    ws_url = get_ws_url(http_url)
    print(f"Connecting to WebSocket: {ws_url}...", file=sys.stderr)
    try:
        ws = websocket.create_connection(ws_url)
        msg = json.loads(ws.recv())
        if msg.get("type") == "auth_required":
            ws.send(json.dumps({
                "type": "auth",
                "access_token": token
            }))
            auth_resp = json.loads(ws.recv())
            if auth_resp.get("type") != "auth_ok":
                print("WebSocket Authentication failed.", file=sys.stderr)
                ws.close()
                sys.exit(1)
            
            # Send save command
            cmd = {
                "id": 1,
                "type": "lovelace/config/save",
                "config": config_data
            }
            url_path = get_url_path(dashboard_key)
            if url_path:
                cmd["url_path"] = url_path
                
            ws.send(json.dumps(cmd))
            result = json.loads(ws.recv())
            ws.close()
            if result.get("success"):
                return True
            else:
                print(f"WebSocket Save failed: {result.get('error')}", file=sys.stderr)
                sys.exit(1)
        else:
            print(f"Unexpected WebSocket message: {msg}", file=sys.stderr)
            ws.close()
            sys.exit(1)
    except Exception as e:
        print(f"WebSocket connection error: {e}", file=sys.stderr)
        sys.exit(1)

def list_dashboards_ws(http_url, token):
    ws_url = get_ws_url(http_url)
    try:
        ws = websocket.create_connection(ws_url)
        msg = json.loads(ws.recv())
        if msg.get("type") == "auth_required":
            ws.send(json.dumps({
                "type": "auth",
                "access_token": token
            }))
            auth_resp = json.loads(ws.recv())
            if auth_resp.get("type") != "auth_ok":
                print("WebSocket Authentication failed.", file=sys.stderr)
                ws.close()
                sys.exit(1)
            
            # Send list command
            cmd = {
                "id": 1,
                "type": "lovelace/dashboards/list"
            }
            ws.send(json.dumps(cmd))
            result = json.loads(ws.recv())
            ws.close()
            if result.get("success"):
                return result.get("result", [])
            else:
                print(f"WebSocket List failed: {result.get('error')}", file=sys.stderr)
                sys.exit(1)
        else:
            print(f"Unexpected WebSocket message: {msg}", file=sys.stderr)
            ws.close()
            sys.exit(1)
    except Exception as e:
        print(f"WebSocket connection error: {e}", file=sys.stderr)
        sys.exit(1)

def cmd_get_state(args, url, token):
    state_data = make_api_request(url, token, f"states/{args.entity_id}")
    print(json.dumps(state_data, indent=2, ensure_ascii=False))

def cmd_list_entities(args, url, token):
    states = make_api_request(url, token, "states")
    filtered = []
    for s in states:
        eid = s.get("entity_id", "")
        if args.domain and not eid.startswith(f"{args.domain}."):
            continue
        filtered.append({
            "entity_id": eid,
            "state": s.get("state", ""),
            "friendly_name": s.get("attributes", {}).get("friendly_name", "")
        })
    print(json.dumps(filtered, indent=2, ensure_ascii=False))

def cmd_download_dashboard(args, url, token):
    config = download_dashboard_ws(url, token, args.dashboard_key)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    print(f"Success: Dashboard config saved to {args.output}")

def cmd_upload_dashboard(args, url, token):
    with open(args.input, "r", encoding="utf-8") as f:
        config_data = json.load(f)
    
    # If the local JSON contains wrapper keys (e.g. data.config), extract it
    if "data" in config_data and "config" in config_data["data"]:
        print("Extracting config from wrapped data format...", file=sys.stderr)
        config_data = config_data["data"]["config"]
        
    upload_dashboard_ws(url, token, args.dashboard_key, config_data)
    print(f"Success: Dashboard {args.dashboard_key} configuration updated and reloaded on Home Assistant!")

def cmd_list_dashboards(args, url, token):
    dashboards = list_dashboards_ws(url, token)
    print(json.dumps(dashboards, indent=2, ensure_ascii=False))

def cmd_check_config(args, url, token):
    print("Triggering configuration check...", file=sys.stderr)
    result = make_api_request(url, token, "services/homeassistant/check_config", method="POST", data={})
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("Configuration check service executed. Check HA notifications or logs for validation result.")

def cmd_restart_core(args, url, token):
    print("WARNING: You are about to restart Home Assistant core.", file=sys.stderr)
    if not args.yes:
        confirm = input("Are you sure you want to proceed? [y/N]: ")
        if confirm.lower() not in ["y", "yes"]:
            print("Abort restart.", file=sys.stderr)
            sys.exit(0)
    result = make_api_request(url, token, "services/homeassistant/restart", method="POST", data={})
    print("Success: Restart service called.", json.dumps(result))

def cmd_call_service(args, url, token):
    if "." not in args.service:
        print("Error: service must be in domain.service format (e.g., light.turn_on)", file=sys.stderr)
        sys.exit(1)
    domain, service = args.service.split(".", 1)
    
    data = {}
    if args.data:
        try:
            data = json.loads(args.data)
        except json.JSONDecodeError as e:
            print(f"Error parsing --data JSON: {e}", file=sys.stderr)
            sys.exit(1)
            
    print(f"Calling service {domain}.{service} with data: {json.dumps(data)}...", file=sys.stderr)
    result = make_api_request(url, token, f"services/{domain}/{service}", method="POST", data=data)
    print(json.dumps(result, indent=2, ensure_ascii=False))

def main():
    parser = argparse.ArgumentParser(description="HA Management Tool - Local/External API client for HA tasks")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # get-state
    p_get = subparsers.add_parser("get-state", help="Get status of an entity")
    p_get.add_argument("entity_id", help="The entity ID (e.g., sensor.temperature)")
    
    # list-entities
    p_list = subparsers.add_parser("list-entities", help="List entities")
    p_list.add_argument("--domain", help="Filter by domain (e.g., sensor, switch)")
    
    # download-dashboard
    p_down = subparsers.add_parser("download-dashboard", help="Download dashboard config via WS API")
    p_down.add_argument("dashboard_key", help="The dashboard key (e.g. lovelace, lovelace.dashboard_mobile)")
    p_down.add_argument("--output", required=True, help="Output JSON path")
    
    # upload-dashboard
    p_up = subparsers.add_parser("upload-dashboard", help="Upload dashboard config and reload via WS API")
    p_up.add_argument("dashboard_key", help="The dashboard key")
    p_up.add_argument("--input", required=True, help="Input JSON file containing config")
    
    # check-config
    subparsers.add_parser("check-config", help="Trigger configuration check")
    
    # list-dashboards
    subparsers.add_parser("list-dashboards", help="List registered dashboards")
    
    # restart-core
    p_rest = subparsers.add_parser("restart-core", help="Restart HA Core")
    p_rest.add_argument("--yes", action="store_true", help="Auto-confirm restart")

    # call-service
    p_srv = subparsers.add_parser("call-service", help="Call a Home Assistant service")
    p_srv.add_argument("service", help="The service to call, format: domain.service (e.g. light.turn_on)")
    p_srv.add_argument("--data", help="JSON data to send as service payload")
    
    args = parser.parse_args()
    
    env_vars = load_env()
    url, token = get_ha_client(env_vars)
    
    if args.command == "get-state":
        cmd_get_state(args, url, token)
    elif args.command == "list-entities":
        cmd_list_entities(args, url, token)
    elif args.command == "download-dashboard":
        cmd_download_dashboard(args, url, token)
    elif args.command == "upload-dashboard":
        cmd_upload_dashboard(args, url, token)
    elif args.command == "list-dashboards":
        cmd_list_dashboards(args, url, token)
    elif args.command == "check-config":
        cmd_check_config(args, url, token)
    elif args.command == "restart-core":
        cmd_restart_core(args, url, token)
    elif args.command == "call-service":
        cmd_call_service(args, url, token)

if __name__ == "__main__":
    main()
