"""Local browser dashboard for chess training runs and self-play replay."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from flask import Flask, jsonify, render_template_string

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
ARTIFACTS = ROOT / "artifacts"
app = Flask(__name__)


def metrics_for(run: Path) -> list[dict]:
    path = run / "metrics.jsonl"
    if not path.exists():
        return []
    result = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            result.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return result


def run_summary(run: Path) -> dict:
    metrics = metrics_for(run)
    latest = next((metric for metric in reversed(metrics) if metric.get("kind") == "eval"), metrics[-1] if metrics else {})
    checkpoints = sorted((run / "checkpoints").glob("*.pt")) if (run / "checkpoints").exists() else []
    return {
        "name": run.name,
        "metrics": metrics,
        "latest": latest,
        "checkpoints": [path.name for path in checkpoints],
        "updated": max((path.stat().st_mtime for path in checkpoints), default=run.stat().st_mtime),
    }


def overview() -> dict:
    runs = [run_summary(path) for path in sorted(RUNS.iterdir()) if path.is_dir()] if RUNS.exists() else []
    replay = {}
    if ARTIFACTS.exists():
        for directory in ARTIFACTS.iterdir():
            if directory.is_dir():
                replay[directory.name] = len(list(directory.glob("*.npz")))
    live_path = ARTIFACTS / "live" / "latest.json"
    try:
        live = json.loads(live_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        live = None
    return {"runs": runs, "replay": replay, "live": live}


@app.get("/api/overview")
def api_overview():
    return jsonify(overview())


@app.get("/")
def index():
    return render_template_string(PAGE)


PAGE = r'''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Chess AI Monitor</title><style>
body{margin:0;background:#10151f;color:#e8edf5;font:15px system-ui,sans-serif}main{max-width:1150px;margin:auto;padding:32px}h1{margin:0;color:#f0c674}.sub{color:#91a0b8}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin:24px 0}.card,section{background:#182131;border:1px solid #29384e;border-radius:12px;padding:16px}.num{font-size:25px;font-weight:700;color:#78d6b1}select{background:#10151f;color:#fff;padding:9px;border-radius:7px;border:1px solid #456}canvas{width:100%;height:280px;background:#121a28;border-radius:9px}.board{display:grid;grid-template-columns:repeat(8,44px);width:352px;border:5px solid #29384e}.sq{height:44px;text-align:center;line-height:44px;font-size:31px}.light{background:#e7d6b6;color:#222}.dark{background:#9a7252;color:#222}.live{display:flex;gap:24px;align-items:start;flex-wrap:wrap}table{width:100%;border-collapse:collapse}td,th{padding:8px;text-align:left;border-bottom:1px solid #29384e}.ok{color:#78d6b1}.muted{color:#91a0b8}</style></head><body><main>
<h1>♞ Chess AI Monitor</h1><p class="sub">Локальный мониторинг: обновляется каждые 5 секунд.</p>
<div id="cards" class="cards"></div><section><label>Run: <select id="run"></select></label><canvas id="chart" width="1060" height="300"></canvas></section>
<section><h2>Live self-play</h2><div id="live" class="muted">Пока нет активной партии.</div></section>
<section><h2>Чекпойнты</h2><div id="checkpoints" class="muted"></div></section><section><h2>Self-play replay</h2><div id="replay" class="muted"></div></section>
</main><script>
let data,selected; const C=document.getElementById('chart'),x=C.getContext('2d');
function fmt(n){return n==null?'—':Number(n).toFixed(3)}
function draw(metrics){x.clearRect(0,0,C.width,C.height);const evals=metrics.filter(m=>m.kind==='eval');if(!evals.length)return;const series=[['loss','#f0c674'],['policy_top1','#78d6b1'],['wdl_accuracy','#7eb6ff']];let vals=series.flatMap(([k])=>evals.map(m=>m[k]).filter(v=>v!=null));let lo=Math.min(...vals),hi=Math.max(...vals);if(lo===hi){lo-=1;hi+=1}series.forEach(([key,color])=>{let a=evals.map(m=>m[key]);x.beginPath();a.forEach((v,i)=>{if(v==null)return;let px=40+i*(C.width-60)/Math.max(a.length-1,1),py=270-(v-lo)*240/(hi-lo);i?x.lineTo(px,py):x.moveTo(px,py)});x.strokeStyle=color;x.lineWidth=2;x.stroke()});x.fillStyle='#91a0b8';x.fillText('loss',8,20);x.fillStyle='#f0c674';x.fillText('● loss',50,20);x.fillStyle='#78d6b1';x.fillText('● policy top-1',120,20);x.fillStyle='#7eb6ff';x.fillText('● WDL accuracy',250,20)}
function render(){let run=data.runs.find(r=>r.name===selected)||data.runs.at(-1);if(!run)return;selected=run.name;let latest=run.latest||{};document.getElementById('cards').innerHTML=[['Шаг',latest.step],['Loss',fmt(latest.loss)],['Policy top‑1',fmt(latest.policy_top1)],['WDL accuracy',fmt(latest.wdl_accuracy)],['Q MAE',fmt(latest.q_mae)]].map(([k,v])=>`<div class=card><div class=muted>${k}</div><div class=num>${v??'—'}</div></div>`).join('');let s=document.getElementById('run');s.innerHTML=data.runs.map(r=>`<option ${r.name===selected?'selected':''}>${r.name}</option>`).join('');s.onchange=()=>{selected=s.value;render()};document.getElementById('checkpoints').innerHTML=run.checkpoints.map(v=>`<span class=ok>${v}</span>`).join('<br>')||'Нет';document.getElementById('replay').innerHTML=Object.entries(data.replay).map(([k,v])=>`${k}: <b>${v}</b> партий`).join('<br>')||'Пока нет';draw(run.metrics)}
function board(fen){let map={P:'♙',N:'♘',B:'♗',R:'♖',Q:'♕',K:'♔',p:'♟',n:'♞',b:'♝',r:'♜',q:'♛',k:'♚'},out='',i=0;fen.split(' ')[0].split('/').forEach(rank=>{for(let c of rank){let n=Number(c)||1;for(let z=0;z<n;z++){out+=`<div class="sq ${((i>>3)+(i&7))%2?'dark':'light'}">${map[c]||''}</div>`;i++}}});return out}
function live(){let v=data.live,el=document.getElementById('live');if(!v){el.textContent='Пока нет активной партии. Запустите generate_selfplay.py.';return}let result=v.status==='finished'?`Партия завершена: ${v.winner||'draw'}`:`Игра ${v.game+1} · ход ${v.ply}`;el.innerHTML=`<div class=live><div class=board>${board(v.fen)}</div><div><b class=ok>${result}</b><p>Последний ход: ${v.last_move?.san||'—'} (${v.last_move?.uci||'—'})</p><p>Оценка корня: ${fmt(v.root_value)}</p><p class=muted>${(v.moves||[]).join(' ')}</p></div></div>`}
let oldrender=render;render=function(){oldrender();live()}
async function refresh(){data=await (await fetch('/api/overview')).json();render()}refresh();setInterval(refresh,5000);
</script></body></html>'''


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8501)
    args = parser.parse_args()
    app.run(host=args.host, port=args.port, debug=False)
