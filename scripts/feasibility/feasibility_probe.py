"""Feasibility probes for the FO sourcing pipeline. Read-only, no data sent."""
import socket, subprocess, sys, json, urllib.request, urllib.error, ssl, time

UA = "polarity-fo-rag-feasibility/0.1 (ahsannhu17@gmail.com)"

def line(t): print("\n" + "="*8 + " " + t + " " + "="*8)

# ---- 1. MX lookup capability ----
line("MX LOOKUP")
mx_hosts = {}
try:
    import dns.resolver  # noqa
    have_dnspython = True
except Exception:
    have_dnspython = False
print("dnspython available:", have_dnspython)

def mx_lookup(domain):
    if have_dnspython:
        import dns.resolver
        try:
            ans = dns.resolver.resolve(domain, "MX")
            return sorted([(r.preference, str(r.exchange).rstrip(".")) for r in ans])
        except Exception as e:
            return f"ERR {e}"
    else:
        try:
            out = subprocess.run(["nslookup", "-type=mx", domain],
                                 capture_output=True, text=True, timeout=15).stdout
            hosts = []
            for ln in out.splitlines():
                if "mail exchanger" in ln.lower():
                    hosts.append(ln.split("=")[-1].strip())
            return hosts or f"RAW:\n{out[:500]}"
        except Exception as e:
            return f"ERR {e}"

for d in ["gmail.com", "waltonfamilyfoundation.org", "tlcapital.com"]:
    r = mx_lookup(d)
    mx_hosts[d] = r
    print(f"  {d}: {r}")

# ---- 2. Outbound port 25 reachability (the make-or-break test) ----
line("OUTBOUND PORT 25")
# pick a resolved MX host to try
targets = []
for d, r in mx_hosts.items():
    if isinstance(r, list) and r:
        first = r[0]
        host = first[1] if isinstance(first, tuple) else str(first)
        targets.append(host)
targets = list(dict.fromkeys(targets))[:3] or ["gmail-smtp-in.l.google.com"]
for host in targets:
    for port in (25, 587):
        try:
            t0 = time.time()
            s = socket.create_connection((host, port), timeout=8)
            banner = b""
            try:
                s.settimeout(4); banner = s.recv(200)
            except Exception:
                pass
            s.close()
            print(f"  {host}:{port} OPEN ({time.time()-t0:.1f}s) banner={banner[:60]!r}")
        except Exception as e:
            print(f"  {host}:{port} BLOCKED/FAIL: {type(e).__name__}: {e}")

# ---- 3. SEC reachability (EDGAR data API + full text search) ----
line("SEC ENDPOINTS")
def get(url, label):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read(4000)
            print(f"  [{label}] {resp.status} {len(data)}+ bytes ({time.time()-t0:.1f}s) {url[:70]}")
            return data
    except urllib.error.HTTPError as e:
        print(f"  [{label}] HTTP {e.code} {url[:70]}")
    except Exception as e:
        print(f"  [{label}] ERR {type(e).__name__}: {e} {url[:70]}")
    return None

d = get("https://data.sec.gov/submissions/CIK0000320193.json", "EDGAR submissions API")
if d:
    try:
        j = json.loads(d.decode("utf-8", "ignore"))
        print("     sample name:", j.get("name"), "| forms present:", bool(j.get("filings")))
    except Exception as e:
        print("     parse note:", e)
get('https://efts.sec.gov/LATEST/search-index?q=%22family+office%22', "EDGAR full-text search")
get('https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=13F&dateb=&owner=include&count=5&output=atom', "EDGAR 13F browse")

# ---- 4. ProPublica Nonprofit Explorer (990-PF) ----
line("PROPUBLICA 990-PF API")
d = get("https://projects.propublica.org/nonprofits/api/v2/search.json?q=family+foundation", "ProPublica search")
if d:
    try:
        j = json.loads(d.decode("utf-8", "ignore"))
        print("     total_results:", j.get("total_results"), "| first:",
              (j.get("organizations") or [{}])[0].get("name"))
    except Exception as e:
        print("     parse note:", e)

print("\nDONE")
