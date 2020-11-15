import argparse, requests, json, sys, os, time

version = float(str(sys.version_info[0]) + "." + str(sys.version_info[1]))

parser = argparse.ArgumentParser()
parser.add_argument("-4", action="store_true", help="only update IPv4 records")
parser.add_argument("--config", default="config.json", help="path to configuration file")
parser.add_argument("--repeat", nargs='?', type=int, default=0, const=600, help="repeat every REPEAT seconds, default is 600 (10 minutes)")

args = parser.parse_args()
onlyIPv4 = getattr(args, '4')

if(version < 3.5):
    raise Exception("This script requires Python 3.5+")

with open(args.config) as config_file:
    config = json.loads(config_file.read())

def getIPs():
    ips = []

    a = ""
    try:
        a = requests.get("https://dns.timknowsbest.com/api/ipv4").text
    except Exception:
        print("Warning: IPv4 not detected.")

    if(a.find(".") > -1):
        ips.append({
            "type": "A",
            "ip": a
        })
    else:
        print("Warning: IPv4 not detected.")

    if not onlyIPv4:
        aaaa = ""
        try:
            aaaa = requests.get("https://api6.ipify.org?format=json").json().get("ip")
        except Exception:
            print("Warning: IPv6 not detected.")

        if(aaaa.find(":") > -1):
            ips.append({
                "type": "AAAA",
                "ip": aaaa
            })
        else:
            print("Warning: IPv6 not detected.")

    return ips


def commitRecord(ip):
    stale_record_ids = []
    for c in config["cloudflare"]:
        subdomains = c["subdomains"]
        response = cf_api("zones/" + c['zone_id'], "GET", c)
        base_domain_name = response["result"]["name"]
        for subdomain in subdomains:
            exists = False
            record = {
                "type": ip["type"],
                "name": subdomain,
                "content": ip["ip"],
                "proxied": c["proxied"]
            }
            list = cf_api(
                "zones/" + c['zone_id'] + "/dns_records?per_page=100&type=" + ip["type"], "GET", c)
            
            full_subdomain = base_domain_name
            if subdomain:
                full_subdomain = subdomain + "." + full_subdomain
            
            dns_id = ""
            for r in list["result"]:
                if (r["name"] == full_subdomain):
                    exists = True
                    if (r["content"] != ip["ip"]):
                        if (dns_id == ""):
                            dns_id = r["id"]
                        else:
                            stale_record_ids.append(r["id"])
            if(exists == False):
                print("Adding new record " + str(record))
                response = cf_api(
                    "zones/" + c['zone_id'] + "/dns_records", "POST", c, {}, record)
            elif(dns_id != ""):
                # Only update if the record content is different
                print("Updating record " + str(record))
                response = cf_api(
                    "zones/" + c['zone_id'] + "/dns_records/" + dns_id, "PUT", c, {}, record)

    # Delete duplicate, stale records
    for identifier in stale_record_ids:
        print("Deleting stale record " + str(identifier))
        response = cf_api(
            "zones/" + c['zone_id'] + "/dns_records/" + identifier, "DELETE", c)

    return True


def cf_api(endpoint, method, config, headers={}, data=False):
    api_token = config['authentication']['api_token']
    if api_token != '' and api_token != 'api_token_here':
        headers = {
            "Authorization": "Bearer " + api_token,
            **headers
        }
    else:
        headers = {
            "X-Auth-Email": config['authentication']['api_key']['account_email'],
            "X-Auth-Key": config['authentication']['api_key']['api_key'],        
        }

    if(data == False):
        response = requests.request(
            method, "https://api.cloudflare.com/client/v4/" + endpoint, headers=headers)
    else:
        response = requests.request(
            method, "https://api.cloudflare.com/client/v4/" + endpoint, headers=headers, json=data)

    return response.json()

def updateIPs():
    for ip in getIPs():
        commitRecord(ip)

if(args.repeat > 0):
    delay = args.repeat
    print("Updating records every", delay, "seconds")
    updateIPs()
    next_time = time.time() + delay
    while True:
        time.sleep(max(0, next_time - time.time()))
        updateIPs()
        next_time += (time.time() - next_time) // delay * delay + delay
else:
    updateIPs()
