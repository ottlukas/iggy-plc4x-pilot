import os
import re
import socket
import time
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import docker
import httpx
from docker.errors import DockerException, NotFound
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.requests import Request
from fastapi.responses import JSONResponse


PROJECT = os.getenv("COMPOSE_PROJECT_NAME", "iggy-plc4x-pilot")
CONFIG_PATH = Path(os.getenv("PILOT_CONFIG", "/app/config.toml"))
FLOW_SERVICES = ["modbus-simulator", "plc4x-bridge", "mqtt-to-iggy", "iggy-to-iotdb"]
INFRA_SERVICES = ["bifromq", "iggy", "iotdb", "superset"]
ALL_SERVICES = INFRA_SERVICES[:1] + ["iggy", "iotdb"] + FLOW_SERVICES + ["superset"]
PORTS = {
    "bifromq": "1883",
    "iggy": "8090",
    "iotdb": "6667, 18080",
    "modbus-simulator": "502 (internal)",
    "plc4x-bridge": "internal",
    "mqtt-to-iggy": "internal",
    "iggy-to-iotdb": "internal",
    "superset": "8088",
    "hmi": "8080",
}
POLL_SECONDS = 3
PROCESS_STARTED = time.monotonic()
app = FastAPI(title="iggy-plc4x-pilot HMI")


HMI_HTML = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>iggy-plc4x-pilot | Pipeline HMI</title>
<style>
:root{color-scheme:dark;--bg:#1a1c20;--panel:#22252b;--panel2:#282c33;--border:#3a3f47;--text:#d0d4dc;--muted:#929aa6;--green:#2ecc71;--red:#e74c3c;--amber:#f0bd4f;--blue:#4aa3df;--mono:ui-monospace,SFMono-Regular,Consolas,monospace;--sans:"Bahnschrift","DIN Alternate","Arial Narrow",sans-serif}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.4 var(--sans)}header{height:58px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;padding:0 22px;background:#202328;position:sticky;top:0;z-index:3}h1{font-size:17px;letter-spacing:.02em;margin:0;font-weight:650}h1 span{color:var(--muted);font-weight:400}.head-right{display:flex;align-items:center;gap:18px;color:var(--muted);font:12px var(--mono)}main{max-width:1600px;margin:auto;padding:14px 18px 24px}.section-title{display:flex;justify-content:space-between;align-items:center;margin:0 0 10px;text-transform:uppercase;letter-spacing:.08em;font-size:11px;color:#aeb5bf;font-weight:700}.overview{display:grid;grid-template-columns:minmax(220px,1fr) 3fr;gap:12px;margin-bottom:12px}.summary,.flow-wrap,.panel,.service{background:var(--panel);border:1px solid var(--border);border-radius:4px}.summary{display:flex;align-items:center;gap:14px;padding:12px 16px;min-height:86px}.lamp{width:18px;height:18px;border-radius:50%;background:#4b5058;border:2px solid #858b94;flex:none}.lamp.healthy,.dot.healthy{background:var(--green);border-color:var(--green)}.lamp.degraded,.dot.degraded{background:var(--amber);border-color:var(--amber)}.lamp.down,.dot.down{background:var(--red);border-color:var(--red)}.sum-main{font-size:18px;font-weight:700}.sum-sub{color:var(--muted);font:11px var(--mono);margin-top:2px}.flow-wrap{padding:12px;overflow-x:auto}.flow{display:flex;align-items:stretch;min-width:880px}.node{min-width:92px;flex:1;text-align:center;padding:8px 4px 6px;border:1px solid var(--border);background:#292d34;border-radius:3px}.node strong{font:600 11px var(--mono);display:block;white-space:nowrap}.node small{display:block;color:var(--muted);font-size:10px;margin-top:4px}.dot{display:inline-block;width:8px;height:8px;border-radius:50%;border:1px solid #737982;background:#4b5058;margin-bottom:5px}.arrow{align-self:center;position:relative;min-width:18px;height:1px;background:#777e88;flex:1}.arrow:after{content:"";position:absolute;right:0;top:-3px;border-left:6px solid #777e88;border-top:3px solid transparent;border-bottom:3px solid transparent}.arrow.bad{background:var(--red);background-image:linear-gradient(90deg,var(--red) 50%,transparent 50%);background-size:8px 1px}.arrow.bad:after{border-left-color:var(--red)}.columns{display:grid;grid-template-columns:minmax(0,1.65fr) minmax(310px,1fr);gap:12px}.panel{padding:12px;margin-bottom:12px;min-width:0}.service-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px}.service{padding:9px 10px;min-width:0;background:#25282e}.svc-head{display:flex;align-items:center;gap:7px;justify-content:space-between}.svc-name{font:600 11px var(--mono);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.state{font:10px var(--mono);text-transform:uppercase;color:var(--muted)}.state.healthy{color:var(--green)}.state.degraded{color:var(--amber)}.state.down{color:var(--red)}.meta{margin-top:7px;color:var(--muted);font:10px/1.5 var(--mono);overflow-wrap:anywhere}.meta b{color:var(--text);font-weight:400}.table-wrap{overflow-x:auto}table{width:100%;border-collapse:collapse;font:11px var(--mono)}th,td{text-align:left;padding:8px 7px;border-bottom:1px solid #363b43;white-space:nowrap}th{color:var(--muted);font-size:10px;text-transform:uppercase}td.value{font-size:15px;color:var(--text)}.badge{font:10px var(--mono);text-transform:uppercase}.badge.live{color:var(--green)}.badge.stale{color:var(--amber)}.badge.no_data{color:var(--muted)}.panel-top{display:flex;align-items:center;justify-content:space-between;gap:8px}.actions{display:flex;gap:7px}.btn,select{height:30px;border:1px solid #515761;background:#292d34;color:var(--text);border-radius:3px;padding:0 10px;font:600 11px var(--mono)}button{cursor:pointer}.btn:hover{border-color:#8b929c}.btn.start{border-color:#43885f}.btn.stop{border-color:#984a45}.btn:disabled{opacity:.5;cursor:wait}select{max-width:210px}.log{background:#17191d;border:1px solid #343941;color:#c0c6cf;padding:9px;min-height:135px;max-height:210px;overflow:auto;white-space:pre-wrap;word-break:break-word;font:10px/1.5 var(--mono);margin:9px 0 0}.config{display:grid;grid-template-columns:1fr 1fr;gap:6px 12px;font:10px/1.5 var(--mono)}.config div{min-width:0}.config dt{color:var(--muted)}.config dd{margin:0;overflow-wrap:anywhere}.tags{grid-column:1/-1;border-top:1px solid var(--border);padding-top:5px;margin-top:2px}.notice{font:11px var(--mono);color:var(--muted);min-height:16px;margin:7px 0 0}.notice.error{color:var(--red)}.panel-foot{color:var(--muted);font:10px var(--mono);margin-top:7px}footer{border-top:1px solid var(--border);padding-top:9px;color:#727a85;font:10px var(--mono);display:flex;justify-content:space-between}
@media(max-width:1050px){.service-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.columns{grid-template-columns:1fr}}@media(max-width:650px){header{padding:0 12px}.head-right{gap:8px;font-size:10px}main{padding:10px}.overview{grid-template-columns:1fr}.summary{min-height:64px}.service-grid{grid-template-columns:1fr 1fr}.section-title{font-size:10px}.actions{gap:4px}.btn{padding:0 7px;font-size:10px}.config{grid-template-columns:1fr}}
</style>
</head>
<body>
<header><h1>IGGY-PLC4X-PILOT <span>/ PIPELINE HMI</span></h1><div class="head-right"><span id="system">SYSTEM --</span><span>UPDATED <b id="updated">--</b></span></div></header>
<main>
<div class="section-title"><span>01 / Pipeline Overview</span><span id="data-age">DATA AGE --</span></div>
<section class="overview"><div class="summary"><i id="lamp" class="lamp"></i><div><div class="sum-main" id="overall">CONNECTING</div><div class="sum-sub" id="sum-sub">Waiting for first status poll</div></div></div><div class="flow-wrap"><div class="flow" id="flow"></div></div></section>
<div class="columns"><div>
<section class="panel"><div class="section-title"><span>02 / Service Status</span><span id="service-count">-- SERVICES</span></div><div class="service-grid" id="services"></div></section>
<section class="panel"><div class="section-title"><span>04 / Live PLC Readings</span><span id="reading-updated">LAST QUERY --</span></div><div class="table-wrap"><table><thead><tr><th>Tag</th><th>Register</th><th>Value</th><th>Timestamp</th><th>State</th></tr></thead><tbody id="readings"><tr><td colspan="5">Waiting for IoTDB data</td></tr></tbody></table></div><div class="panel-foot" id="reading-note">Last successful PLC value is retained by IoTDB; repeated timestamps indicate no new sample.</div></section>
</div><div>
<section class="panel"><div class="section-title"><span>03 / Flow Control</span><span id="control-state">READY</span></div><div class="actions"><button class="btn start" id="start" onclick="control('start')">START PIPELINE</button><button class="btn stop" id="stop" onclick="control('stop')">STOP PIPELINE</button><button class="btn" onclick="refreshAll()" title="Refresh now">REFRESH</button></div><div id="notice" class="notice" role="status"></div></section>
<section class="panel"><div class="section-title"><span>05 / Diagnostics</span><select id="log-service" aria-label="Log service"></select></div><div class="panel-top"><span class="panel-foot" id="log-updated">LAST LOG FETCH --</span><button class="btn" onclick="loadLogs()">LOAD LOGS</button></div><pre class="log" id="logs">Select a service to view its recent container logs.</pre></section>
<section class="panel"><div class="section-title"><span>06 / Configuration</span><span>READ ONLY</span></div><dl class="config" id="config"></dl></section>
</div></div>
<footer><span>IGGY-PLC4X-PILOT / CONTROL ROOM</span><span>HMI 1.0 / POLL 3S</span></footer>
</main>
<script>
const order=['modbus-simulator','plc4x-bridge','bifromq','mqtt-to-iggy','iggy','iggy-to-iotdb','iotdb','superset'];
let lastStatus=null,lastReadingTs=null;
const esc=s=>String(s??'--').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function age(ts){if(!ts)return '--';const seconds=Math.max(0,Math.floor((Date.now()-new Date(ts).getTime())/1000));return seconds<60?`${seconds}s`:`${Math.floor(seconds/60)}m ${seconds%60}s`}
function buildFlow(services){const map=Object.fromEntries(services.map(s=>[s.name,s]));const labels={'modbus-simulator':'MODBUS PLC','plc4x-bridge':'PLC4X BRIDGE','bifromq':'BIFROMQ MQTT','mqtt-to-iggy':'MQTT → IGGY','iggy':'IGGY STREAM','iggy-to-iotdb':'IGGY → IoTDB','iotdb':'IoTDB','superset':'SUPERSET'};return order.map((name,i)=>{const s=map[name]||{health:'down',status:'missing'};const node=`<div class="node"><i class="dot ${esc(s.health)}"></i><strong>${labels[name]}</strong><small>${esc(s.status)}</small></div>`;return node+(i<order.length-1?`<i class="arrow ${s.health==='down'?'bad':''}"></i>`:'')}).join('')}
function renderServices(rows){document.getElementById('services').innerHTML=rows.map(s=>`<article class="service"><div class="svc-head"><span class="svc-name" title="${esc(s.name)}">${esc(s.name)}</span><span class="state ${esc(s.health)}">${esc(s.status)}</span></div><div class="meta">HEALTH <b>${esc(s.health)}</b><br>UPTIME <b>${esc(s.uptime)}</b><br>PORT <b>${esc(s.port)}</b><br>ACTIVITY <b>${esc(s.last_activity||'--')}</b></div></article>`).join('');document.getElementById('service-count').textContent=`${rows.length} SERVICES`}
async function json(url,options){const response=await fetch(url,options);const body=await response.json();if(!response.ok)throw new Error(body.detail||body.error||response.statusText);return body}
async function refreshStatus(){const data=await json('/api/pipeline/status');lastStatus=data;document.getElementById('lamp').className=`lamp ${data.health}`;document.getElementById('overall').textContent=data.label;document.getElementById('sum-sub').textContent=`${data.running}/${data.total} RUNNING · ${data.health.toUpperCase()}`;document.getElementById('system').textContent=`SYSTEM ${data.health.toUpperCase()}`;document.getElementById('updated').textContent=new Date(data.updated_at).toLocaleTimeString();document.getElementById('flow').innerHTML=buildFlow(data.services);renderServices(data.services);document.getElementById('data-age').textContent=`DATA AGE ${age(lastReadingTs)}`;}
function renderReadings(data){const body=document.getElementById('readings');if(!data.readings?.length){body.innerHTML=`<tr><td colspan="5">${esc(data.message||'No readings available')}</td></tr>`;return}body.innerHTML=data.readings.map(r=>`<tr><td>${esc(r.name)}</td><td>${esc(r.address)}</td><td class="value">${esc(r.value)}</td><td>${esc(r.timestamp||'--')}</td><td><span class="badge ${esc(r.status)}">${esc(r.status.replace('_',' '))}</span></td></tr>`).join('');lastReadingTs=data.latest_timestamp||null;document.getElementById('data-age').textContent=`DATA AGE ${age(lastReadingTs)}`}
async function refreshReadings(){const data=await json('/api/readings');renderReadings(data);document.getElementById('reading-updated').textContent=`LAST QUERY ${new Date(data.updated_at).toLocaleTimeString()}`}
async function refreshAll(){try{await Promise.all([refreshStatus(),refreshReadings()])}catch(e){document.getElementById('system').textContent='SYSTEM DATA STALE';document.getElementById('lamp').className='lamp degraded';document.getElementById('notice').className='notice error';document.getElementById('notice').textContent=`Refresh failed: ${e.message}`}}
async function control(action){const running=lastStatus?.services?.filter(s=>s.name!=='hmi'&&s.status==='running')||[];if(action==='stop'&&running.some(s=>s.uptime_seconds>300)&&!confirm('Pipeline has been running for more than 5 minutes. Stop the data flow?'))return;const button=document.getElementById(action);button.disabled=true;document.getElementById('control-state').textContent=`${action.toUpperCase()}ING…`;document.getElementById('notice').className='notice';document.getElementById('notice').textContent=`Requesting pipeline ${action}…`;try{const result=await json(`/api/pipeline/${action}`,{method:'POST'});document.getElementById('notice').textContent=result.message;await refreshAll()}catch(e){document.getElementById('notice').className='notice error';document.getElementById('notice').textContent=`${action.toUpperCase()} failed: ${e.message}`}finally{button.disabled=false;document.getElementById('control-state').textContent='READY'}}
async function loadLogs(){const name=document.getElementById('log-service').value;try{const data=await json(`/api/logs?service=${encodeURIComponent(name)}&lines=50`);document.getElementById('logs').textContent=data.lines.join('\n')||'No log lines available.';document.getElementById('log-updated').textContent=`LAST LOG FETCH ${new Date().toLocaleTimeString()}`}catch(e){document.getElementById('logs').textContent=`Unable to load logs: ${e.message}`}}
async function loadConfig(){try{const data=await json('/api/config');const rows=[['PLC endpoint',data.plc.endpoint],['PLC device',data.plc.device],['Poll interval',`${data.plc.poll_interval_ms} ms`],['MQTT',`${data.mqtt.host}:${data.mqtt.port} / ${data.mqtt.topic_prefix}`],['Iggy',`${data.iggy.address} / ${data.iggy.stream} / ${data.iggy.topic}`],['IoTDB',`${data.iotdb.endpoint} / ${data.iotdb.device_prefix}`]];document.getElementById('config').innerHTML=rows.map(([k,v])=>`<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join('')+`<div class="tags"><dt>TAGS</dt><dd>${data.plc.tags.map(t=>`${esc(t.name)} · ${esc(t.address)}`).join('<br>')}</dd></div>`}catch(e){document.getElementById('config').textContent=`Configuration unavailable: ${e.message}`}}
async function init(){try{const data=await json('/api/services');document.getElementById('log-service').innerHTML=data.map(s=>`<option value="${esc(s.name)}">${esc(s.name)}</option>`).join('');}catch{}await loadConfig();await refreshAll();}
init();setInterval(refreshAll,3000);setInterval(()=>{if(document.getElementById('log-service').value)loadLogs()},15000);
</script>
</body></html>'''


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_config() -> dict[str, Any]:
    try:
        with CONFIG_PATH.open("rb") as config_file:
            return tomllib.load(config_file)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise HTTPException(status_code=500, detail=f"Unable to read pipeline config: {error}") from error


def docker_client() -> docker.DockerClient:
    try:
        client = docker.from_env(timeout=3)
        client.ping()
        return client
    except DockerException as error:
        raise HTTPException(status_code=503, detail=f"Docker API unavailable: {error}") from error


def containers_by_service(client: docker.DockerClient) -> dict[str, Any]:
    try:
        containers = client.containers.list(
            all=True, filters={"label": f"com.docker.compose.project={PROJECT}"}
        )
        return {
            container.labels.get("com.docker.compose.service"): container
            for container in containers
            if container.labels.get("com.docker.compose.service")
        }
    except DockerException as error:
        raise HTTPException(status_code=503, detail=f"Unable to inspect Compose services: {error}") from error


def tcp_probe(host: str, port: int, timeout: float = 0.7) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def http_probe(urls: list[str], auth: tuple[str, str] | None = None) -> bool:
    try:
        with httpx.Client(timeout=1.5, follow_redirects=True) as client:
            for url in urls:
                try:
                    response = client.get(url, auth=auth)
                    if response.status_code < 500:
                        return response.is_success
                except httpx.HTTPError:
                    continue
    except httpx.HTTPError:
        pass
    return False


def recent_logs(container: Any, lines: int = 50) -> list[str]:
    try:
        result = container.logs(tail=lines, timestamps=True)
        return result.decode("utf-8", errors="replace").splitlines()
    except DockerException:
        return []


def log_activity(lines: list[str]) -> str | None:
    if not lines:
        return None
    match = re.match(r"^(\S+)", lines[-1])
    return match.group(1) if match else None


def has_recent_issue(lines: list[str], seconds: int = 15) -> bool:
    now = datetime.now(timezone.utc)
    for line in reversed(lines):
        if "warn" not in line.lower() and "error" not in line.lower():
            continue
        match = re.match(r"^(\S+)", line)
        try:
            timestamp = datetime.fromisoformat(match.group(1).replace("Z", "+00:00")) if match else None
        except ValueError:
            timestamp = None
        if timestamp is None or (now - timestamp).total_seconds() <= seconds:
            return True
    return False


def probe_service(name: str, container: Any, config: dict[str, Any]) -> tuple[str, str | None]:
    if name == "bifromq":
        healthy = tcp_probe("bifromq", 1883)
    elif name == "iggy":
        healthy = tcp_probe("iggy", 8090)
    elif name == "iotdb":
        credentials = config["iotdb"]
        healthy = http_probe(["http://iotdb:18080/rest/v2/settings"], (credentials["username"], credentials["password"]))
        if not healthy:
            healthy = tcp_probe("iotdb", 6667)
    elif name == "modbus-simulator":
        healthy = tcp_probe("modbus-simulator", 502)
    elif name == "superset":
        healthy = http_probe(["http://superset:8088/health"])
    else:
        lines = recent_logs(container, 100)
        return ("degraded" if has_recent_issue(lines) else "healthy"), log_activity(lines)
    return ("healthy" if healthy else "degraded"), None


def service_status(name: str, container: Any | None, config: dict[str, Any]) -> dict[str, Any]:
    if name == "hmi":
        elapsed = int(time.monotonic() - PROCESS_STARTED)
        return {
            "name": name, "status": "running", "health": "healthy", "uptime": format_uptime(elapsed),
            "uptime_seconds": elapsed, "port": PORTS[name], "last_activity": now_iso(),
        }
    if container is None:
        return {
            "name": name, "status": "not_created", "health": "down", "uptime": "--",
            "uptime_seconds": 0, "port": PORTS[name], "last_activity": None,
        }
    container.reload()
    status = container.status
    if status != "running":
        return {
            "name": name, "status": status, "health": "down", "uptime": "--", "uptime_seconds": 0,
            "port": PORTS[name], "last_activity": log_activity(recent_logs(container, 1)),
        }
    health, activity = probe_service(name, container, config)
    started = container.attrs.get("State", {}).get("StartedAt")
    try:
        start_time = datetime.fromisoformat(started.replace("Z", "+00:00"))
        uptime_seconds = max(0, int((datetime.now(timezone.utc) - start_time).total_seconds()))
    except (ValueError, AttributeError):
        uptime_seconds = 0
    if activity is None:
        activity = log_activity(recent_logs(container, 1))
    return {
        "name": name, "status": status, "health": health, "uptime": format_uptime(uptime_seconds),
        "uptime_seconds": uptime_seconds, "port": PORTS[name], "last_activity": activity,
    }


def format_uptime(seconds: int) -> str:
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)
    prefix = f"{days}d " if days else ""
    return f"{prefix}{hours:02d}:{minutes:02d}:{secs:02d}"


def all_service_statuses(config: dict[str, Any]) -> list[dict[str, Any]]:
    containers = containers_by_service(docker_client())
    return [service_status(name, containers.get(name), config) for name in ALL_SERVICES] + [service_status("hmi", None, config)]


def get_readings(config: dict[str, Any]) -> dict[str, Any]:
    plc, iotdb = config["plc"], config["iotdb"]
    device = f"{iotdb['device_prefix']}.{plc['device']}"
    tags = plc["tags"]
    names = [tag["name"] for tag in tags]
    sql = f"SELECT {', '.join(names)} FROM {device} ORDER BY TIME DESC LIMIT 1"
    query_url = re.sub(r"/nonQuery/?$", "/query", iotdb["endpoint"])
    updated = now_iso()
    try:
        response = httpx.post(
            query_url,
            json={"sql": sql},
            auth=(iotdb["username"], iotdb["password"]),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=2.5,
        )
        response.raise_for_status()
        result = response.json()
    except (httpx.HTTPError, ValueError) as error:
        return {"status": "no_data", "readings": [], "message": f"IoTDB query unavailable: {error}", "updated_at": updated, "latest_timestamp": None}

    timestamps = result.get("timestamps") or []
    columns = result.get("columnNames") or result.get("columns") or []
    rows = result.get("values") or result.get("data") or []
    if isinstance(rows, dict):
        rows = [rows]
    first = rows[0] if rows else None
    if isinstance(first, dict):
        values = first
        timestamp = first.get("Time") or first.get("time") or (timestamps[0] if timestamps else None)
    elif isinstance(first, list):
        values = dict(zip(columns, first)) if columns else {}
        if "Time" in values:
            timestamp = values.pop("Time")
        else:
            timestamp = timestamps[0] if timestamps else (first[0] if len(first) > len(names) else None)
            if not columns and len(first) == len(names) + 1:
                first_values = first[1:]
            else:
                first_values = first
            if not values:
                values = dict(zip(names, first_values))
    else:
        values, timestamp = {}, timestamps[0] if timestamps else None

    if timestamp is None or not values:
        return {"status": "no_data", "readings": [], "message": "No PLC readings have reached IoTDB yet.", "updated_at": updated, "latest_timestamp": None}
    timestamp_value = int(timestamp) if str(timestamp).isdigit() else timestamp
    if isinstance(timestamp_value, (int, float)):
        timestamp_dt = datetime.fromtimestamp(timestamp_value / 1000, timezone.utc)
    else:
        try:
            timestamp_dt = datetime.fromisoformat(str(timestamp_value).replace("Z", "+00:00"))
        except ValueError:
            timestamp_dt = datetime.now(timezone.utc)
    age_seconds = max(0, (datetime.now(timezone.utc) - timestamp_dt).total_seconds())
    state = "live" if age_seconds <= plc["poll_interval_ms"] * 3 / 1000 else "stale"
    readings = [{
        "name": tag["name"],
        "address": tag["address"],
        "value": values.get(tag["name"], "--"),
        "timestamp": timestamp_dt.isoformat(),
        "status": state,
    } for tag in tags]
    return {
        "status": state, "readings": readings, "updated_at": updated,
        "latest_timestamp": timestamp_dt.isoformat(), "age_seconds": round(age_seconds, 1), "sql": sql,
    }


@app.exception_handler(Exception)
def unhandled_error(_request: Request, error: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": f"Internal HMI error: {error}"})


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return HMI_HTML


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "ts": now_iso()}


@app.get("/api/config")
def config_endpoint() -> dict[str, Any]:
    config = get_config()
    return {
        "plc": config["plc"],
        "mqtt": {key: config["mqtt"][key] for key in ("host", "port", "topic_prefix")},
        "iggy": {key: config["iggy"][key] for key in ("address", "stream", "topic")},
        "iotdb": {key: config["iotdb"][key] for key in ("endpoint", "device_prefix")},
    }


@app.get("/api/services")
def services_endpoint() -> list[dict[str, Any]]:
    return all_service_statuses(get_config())


@app.get("/api/services/{service_name}")
def service_endpoint(service_name: str) -> dict[str, Any]:
    if service_name not in ALL_SERVICES and service_name != "hmi":
        raise HTTPException(status_code=404, detail=f"Unknown service: {service_name}")
    config = get_config()
    if service_name == "hmi":
        return service_status("hmi", None, config)
    containers = containers_by_service(docker_client())
    return service_status(service_name, containers.get(service_name), config)


@app.get("/api/pipeline/status")
def pipeline_status() -> dict[str, Any]:
    config = get_config()
    services = all_service_statuses(config)
    pipeline_services = [service for service in services if service["name"] != "hmi"]
    running = sum(service["status"] == "running" for service in pipeline_services)
    if any(service["health"] == "down" for service in pipeline_services):
        health_state, label = "down", "PIPELINE ATTENTION"
    elif any(service["health"] == "degraded" for service in pipeline_services):
        health_state, label = "degraded", "PIPELINE DEGRADED"
    else:
        health_state, label = "healthy", "PIPELINE HEALTHY"
    return {
        "health": health_state, "label": label, "running": running, "total": len(pipeline_services),
        "services": services, "updated_at": now_iso(),
    }


@app.get("/api/readings")
def readings_endpoint() -> dict[str, Any]:
    return get_readings(get_config())


def control_pipeline(action: str, services: list[str]) -> dict[str, Any]:
    client = docker_client()
    containers = containers_by_service(client)
    ordered = services if action == "start" else list(reversed(services))
    selected = [(name, containers.get(name)) for name in ordered]
    missing = [name for name, container in selected if container is None]
    if missing:
        raise HTTPException(status_code=503, detail=f"Compose containers not found for project {PROJECT}: {', '.join(missing)}")
    target = [(name, container) for name, container in selected if (container.status != "running" if action == "start" else container.status == "running")]
    if not target:
        state = "running" if action == "start" else "stopped"
        raise HTTPException(status_code=409, detail=f"All selected data-flow services are already {state}.")
    changed = []
    try:
        for name, container in target:
            if action == "start":
                container.start()
            else:
                container.stop(timeout=10)
            changed.append(name)
    except DockerException as error:
        raise HTTPException(status_code=500, detail=f"Pipeline {action} failed after {', '.join(changed) or 'no services'}: {error}") from error
    return {"status": "ok", "action": action, "services": changed, "message": f"Pipeline {action} requested for: {', '.join(changed)}"}


@app.post("/api/pipeline/start")
def pipeline_start() -> dict[str, Any]:
    return control_pipeline("start", FLOW_SERVICES)


@app.post("/api/pipeline/stop")
def pipeline_stop() -> dict[str, Any]:
    services = FLOW_SERVICES if os.getenv("STOP_SIMULATOR", "true").lower() in ("1", "true", "yes") else FLOW_SERVICES[1:]
    return control_pipeline("stop", services)


@app.post("/api/plc/start")
def plc_start() -> dict[str, Any]:
    return control_pipeline("start", ["modbus-simulator", "plc4x-bridge"])


@app.post("/api/plc/stop")
def plc_stop() -> dict[str, Any]:
    return control_pipeline("stop", ["modbus-simulator", "plc4x-bridge"])


@app.get("/api/plc/status")
def plc_status() -> dict[str, Any]:
    config = get_config()
    containers = containers_by_service(docker_client())
    statuses = [service_status(name, containers.get(name), config) for name in ("modbus-simulator", "plc4x-bridge")]
    return {"services": statuses, "running": all(service["status"] == "running" for service in statuses)}


@app.get("/api/logs")
@app.get("/api/plc/logs")
def logs_endpoint(service: str = Query("plc4x-bridge"), lines: int = Query(50, ge=1, le=500)) -> dict[str, Any]:
    if service not in ALL_SERVICES:
        raise HTTPException(status_code=404, detail=f"Unknown service: {service}")
    containers = containers_by_service(docker_client())
    container = containers.get(service)
    if container is None:
        raise HTTPException(status_code=404, detail=f"Container for {service} is not created.")
    try:
        log_lines = recent_logs(container, lines)
    except DockerException as error:
        raise HTTPException(status_code=503, detail=f"Unable to read {service} logs: {error}") from error
    return {"service": service, "lines": log_lines, "updated_at": now_iso()}
