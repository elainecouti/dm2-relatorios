"""
Dashboard genérico Meta Ads — funciona para qualquer conta.
Agrupa campanhas por objetivo, mostra KPIs, tabela de campanhas,
top criativos com thumbnail + link, gráfico diário.
"""

import json
import os
from datetime import datetime, timezone, timedelta

import requests
from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN = os.environ["META_ACCESS_TOKEN"]
API_VERSION = "v21.0"
API_BASE = f"https://graph.facebook.com/{API_VERSION}"


def meta_get(endpoint, params=None):
    params = params or {}
    params["access_token"] = ACCESS_TOKEN
    url = f"{API_BASE}/{endpoint}"
    results = []
    while url:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            print(f"  ⚠ API error: {data['error'].get('message', '')}")
            return {"error": data["error"]}
        if "data" in data:
            results.extend(data["data"])
        else:
            return data
        url = data.get("paging", {}).get("next")
        params = {}
    return results


def extract_action(actions, action_type):
    if not actions:
        return 0
    for a in actions:
        if a.get("action_type") == action_type:
            return int(float(a.get("value", 0)))
    return 0


def classify_objective(objective):
    """Mapeia objetivo da API para label amigável."""
    mapping = {
        "OUTCOME_TRAFFIC": "Tráfego",
        "LINK_CLICKS": "Tráfego",
        "OUTCOME_ENGAGEMENT": "Engajamento",
        "POST_ENGAGEMENT": "Engajamento",
        "OUTCOME_AWARENESS": "Alcance",
        "REACH": "Alcance",
        "BRAND_AWARENESS": "Alcance",
        "OUTCOME_LEADS": "Leads",
        "LEAD_GENERATION": "Leads",
        "OUTCOME_SALES": "Vendas",
        "CONVERSIONS": "Vendas",
        "PRODUCT_CATALOG_SALES": "Vendas",
        "MESSAGES": "Mensagens",
        "VIDEO_VIEWS": "Vídeo",
        "OUTCOME_APP_PROMOTION": "App",
    }
    return mapping.get(objective, objective or "Outros")


OBJ_COLORS = {
    "Tráfego": "#1D71B8",
    "Engajamento": "#9333ea",
    "Alcance": "#f59e0b",
    "Leads": "#00A19A",
    "Vendas": "#22c55e",
    "Mensagens": "#06b6d4",
    "Vídeo": "#ec4899",
    "App": "#6366f1",
    "Outros": "#6b7280",
}


def get_ad_creative_info(ad):
    """Extrai copy, título, descrição, thumbnail e permalink."""
    creative = ad.get("creative", {})
    body = creative.get("body", "")
    title = creative.get("title", "")
    thumbnail = creative.get("thumbnail_url", "")
    cta = creative.get("call_to_action_type", "")
    description = ""
    permalink = ad.get("preview_shareable_link", "")

    story_id = creative.get("effective_object_story_id", "")
    if story_id and not permalink:
        parts = story_id.split("_")
        if len(parts) == 2:
            permalink = f"https://www.facebook.com/{parts[0]}/posts/{parts[1]}"

    if thumbnail and "fbcdn" in thumbnail:
        if "?" in thumbnail:
            thumbnail += "&width=480"
        else:
            thumbnail += "?width=480"

    oss = creative.get("object_story_spec", {})
    if oss:
        vd = oss.get("video_data", {})
        if vd:
            body = body or vd.get("message", "")
            title = title or vd.get("title", "")
            description = vd.get("link_description", "")
            if vd.get("image_url"):
                thumbnail = vd["image_url"]
        ld = oss.get("link_data", {})
        if ld:
            body = body or ld.get("message", "")
            title = title or ld.get("name", "")
            description = description or ld.get("description", "")
            if ld.get("picture") and not thumbnail:
                thumbnail = ld["picture"]

    afs = creative.get("asset_feed_spec", {})
    if afs:
        bodies = afs.get("bodies", [])
        titles = afs.get("titles", [])
        descs = afs.get("descriptions", [])
        if bodies and not body:
            body = bodies[0].get("text", "")
        if titles and not title:
            title = titles[0].get("text", "")
        if descs and not description:
            description = descs[0].get("text", "")
        images = afs.get("images", [])
        if images and (not thumbnail or "fbcdn" in thumbnail):
            img_url = images[0].get("url", "")
            if img_url:
                thumbnail = img_url

    return {
        "body": body, "title": title, "description": description,
        "thumbnail": thumbnail, "cta": cta, "permalink": permalink,
    }


def fetch_all(account_id):
    print(f"  Buscando dados...")
    account_info = meta_get(f"act_{account_id}", {
        "fields": "spend_cap,amount_spent,balance,account_status,currency,name",
    })

    campaigns = meta_get(f"act_{account_id}/campaigns", {
        "fields": "name,status,effective_status,objective,daily_budget,lifetime_budget",
        "limit": 100,
    })
    if isinstance(campaigns, dict): campaigns = []

    camp_insights = meta_get(f"act_{account_id}/insights", {
        "fields": "campaign_name,campaign_id,impressions,reach,clicks,spend,ctr,cpc,cpm,frequency,actions",
        "level": "campaign",
        "date_preset": "maximum",
    })
    if isinstance(camp_insights, dict): camp_insights = []

    ads = meta_get(f"act_{account_id}/ads", {
        "fields": "name,status,effective_status,campaign_id,adset_id,creative{id,title,body,call_to_action_type,object_story_spec,asset_feed_spec,thumbnail_url,effective_object_story_id},preview_shareable_link",
        "limit": 100,
    })
    if isinstance(ads, dict): ads = []

    ad_insights = meta_get(f"act_{account_id}/insights", {
        "fields": "ad_name,ad_id,campaign_name,campaign_id,impressions,reach,clicks,spend,ctr,cpc,actions",
        "level": "ad",
        "date_preset": "maximum",
        "limit": 200,
    })
    if isinstance(ad_insights, dict): ad_insights = []

    daily = meta_get(f"act_{account_id}/insights", {
        "fields": "spend,impressions,clicks,ctr,actions,date_start",
        "date_preset": "last_7d",
        "level": "account",
        "time_increment": "1",
    })
    if isinstance(daily, dict): daily = []

    total = meta_get(f"act_{account_id}/insights", {
        "fields": "spend,impressions,clicks,ctr,cpc,cpm,reach,frequency,actions",
        "date_preset": "maximum",
        "level": "account",
    })
    if isinstance(total, dict): total = []

    return {
        "account_info": account_info if isinstance(account_info, dict) else {},
        "campaigns": campaigns,
        "camp_insights": camp_insights,
        "ads": ads,
        "ad_insights": ad_insights,
        "daily": daily,
        "total": total[0] if total else {},
    }


def process(data):
    camps_map = {c["id"]: c for c in data["campaigns"]}

    # Ad creative lookup
    ad_creative_lookup = {}
    for ad in data["ads"]:
        key = (ad["name"], ad.get("campaign_id", ""))
        if key not in ad_creative_lookup:
            ad_creative_lookup[key] = get_ad_creative_info(ad)
        if ad["name"] not in ad_creative_lookup:
            ad_creative_lookup[ad["name"]] = get_ad_creative_info(ad)

    # Campaign-level
    camp_rows = []
    for row in data["camp_insights"]:
        cid = row.get("campaign_id", "")
        camp = camps_map.get(cid, {})
        objective = classify_objective(camp.get("objective", ""))
        status = camp.get("effective_status", "UNKNOWN")
        spend = float(row.get("spend", 0))
        clicks = int(row.get("clicks", 0))
        reach = int(row.get("reach", 0))
        impressions = int(row.get("impressions", 0))
        ctr = float(row.get("ctr", 0))
        conversations = extract_action(row.get("actions"), "onsite_conversion.messaging_conversation_started_7d")
        leads = extract_action(row.get("actions"), "lead")
        purchases = extract_action(row.get("actions"), "purchase") or extract_action(row.get("actions"), "omni_purchase")
        link_clicks = extract_action(row.get("actions"), "link_click")
        conversions = conversations or leads or purchases

        camp_rows.append({
            "id": cid, "name": row.get("campaign_name", ""), "status": status,
            "objective": objective, "spend": spend, "clicks": clicks,
            "reach": reach, "impressions": impressions, "ctr": ctr,
            "conversations": conversations, "leads": leads, "purchases": purchases,
            "link_clicks": link_clicks, "conversions": conversions,
            "cpl": spend / conversions if conversions > 0 else 0,
        })

    # Ad-level (top creatives)
    ad_rows = []
    for row in data["ad_insights"]:
        ad_name = row.get("ad_name", "")
        cname = row.get("campaign_name", "")
        cid = row.get("campaign_id", "")
        camp = camps_map.get(cid, {})
        creative = ad_creative_lookup.get((ad_name, cid)) or ad_creative_lookup.get(ad_name) or {}
        spend = float(row.get("spend", 0))
        conversations = extract_action(row.get("actions"), "onsite_conversion.messaging_conversation_started_7d")
        leads_ad = extract_action(row.get("actions"), "lead")
        purchases_ad = extract_action(row.get("actions"), "purchase") or extract_action(row.get("actions"), "omni_purchase")
        conversions = conversations or leads_ad or purchases_ad

        ad_rows.append({
            "name": ad_name, "campaign": cname,
            "objective": classify_objective(camp.get("objective", "")),
            "spend": spend,
            "impressions": int(row.get("impressions", 0)),
            "reach": int(row.get("reach", 0)),
            "clicks": int(row.get("clicks", 0)),
            "ctr": float(row.get("ctr", 0)),
            "conversions": conversions,
            "cpl": spend / conversions if conversions > 0 else 0,
            "thumbnail": creative.get("thumbnail", ""),
            "permalink": creative.get("permalink", ""),
            "body": creative.get("body", ""),
            "title": creative.get("title", ""),
        })

    # Daily
    daily_chart = []
    for row in data["daily"]:
        convs = extract_action(row.get("actions"), "onsite_conversion.messaging_conversation_started_7d")
        sp = float(row.get("spend", 0))
        daily_chart.append({
            "date": row.get("date_start", "")[-5:].replace("-", "/"),
            "spend": round(sp, 2),
            "clicks": int(row.get("clicks", 0)),
            "conversations": convs,
        })

    # Totals
    t = data["total"]
    total_spend = float(t.get("spend", 0))
    total_reach = int(t.get("reach", 0))
    total_clicks = int(t.get("clicks", 0))
    total_impressions = int(t.get("impressions", 0))
    total_ctr = float(t.get("ctr", 0))
    total_cpc = float(t.get("cpc", 0))
    total_cpm = float(t.get("cpm", 0))
    total_convs = sum(c["conversions"] for c in camp_rows)
    total_cpl = total_spend / total_convs if total_convs > 0 else 0

    active_camps = [c for c in data["campaigns"] if c.get("effective_status") == "ACTIVE"]

    # Balance
    info = data["account_info"]
    spend_cap = int(info.get("spend_cap", 0)) / 100
    amount_spent = int(info.get("amount_spent", 0)) / 100
    balance = int(info.get("balance", 0)) / 100
    remaining = (spend_cap - amount_spent) if spend_cap > 0 else balance

    return {
        "campaigns": camp_rows,
        "ads": ad_rows,
        "daily_chart": daily_chart,
        "balance": {
            "remaining": remaining, "spend_cap": spend_cap, "amount_spent": amount_spent,
            "pct_used": (amount_spent / spend_cap * 100) if spend_cap > 0 else 0,
        },
        "summary": {
            "spend": total_spend, "reach": total_reach, "clicks": total_clicks,
            "impressions": total_impressions, "ctr": total_ctr, "cpc": total_cpc,
            "cpm": total_cpm, "conversions": total_convs, "cpl": total_cpl,
            "active": len(active_camps), "total_camps": len(data["campaigns"]),
        },
        "account_name": info.get("name", ""),
    }


def esc(text):
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("\n", "<br>")


def generate_html(slug, client_info, p):
    now = datetime.now(timezone(timedelta(hours=-3))).strftime("%d/%m/%Y %H:%M")
    s = p["summary"]
    b = p["balance"]
    camps = p["campaigns"]
    ads = p["ads"]
    daily = p["daily_chart"]

    nome = client_info.get("nome", slug)
    subtitle = client_info.get("subtitle", "")

    chart_labels = json.dumps([d["date"] for d in daily])
    chart_spend = json.dumps([d["spend"] for d in daily])
    chart_convs = json.dumps([d["conversations"] for d in daily])
    chart_clicks = json.dumps([d["clicks"] for d in daily])

    # KPI cards
    kpis = [
        ("Investido", f"R$ {s['spend']:,.2f}"),
        ("Alcance", f"{s['reach']:,}"),
        ("Cliques", f"{s['clicks']:,}"),
        ("CTR", f"{s['ctr']:.2f}%"),
        ("CPC", f"R$ {s['cpc']:.2f}"),
        ("CPM", f"R$ {s['cpm']:.2f}"),
        ("Conversões", f"{s['conversions']:,}"),
        ("Custo/Conv", f"R$ {s['cpl']:.2f}" if s['cpl'] > 0 else "—"),
    ]
    kpi_html = ""
    for label, val in kpis:
        kpi_html += f'<div class="kpi"><span class="kpi-v">{val}</span><span class="kpi-l">{label}</span></div>'

    # Campaign table rows
    camps_sorted = sorted(camps, key=lambda x: x["spend"], reverse=True)
    camp_rows_html = ""
    for c in camps_sorted:
        status_dot = "active" if c["status"] == "ACTIVE" else "paused"
        obj_color = OBJ_COLORS.get(c["objective"], "#6b7280")
        camp_rows_html += f"""<tr>
            <td><span class="dot {status_dot}"></span>{esc(c['name'][:45])}</td>
            <td><span class="obj-tag" style="background:{obj_color}">{c['objective']}</span></td>
            <td>R$ {c['spend']:.2f}</td>
            <td>{c['reach']:,}</td>
            <td>{c['clicks']:,}</td>
            <td>{c['ctr']:.2f}%</td>
            <td><strong>{c['conversions']}</strong></td>
            <td>{'R$ '+f"{c['cpl']:.2f}" if c['cpl']>0 else '—'}</td>
        </tr>"""

    # Top creatives (by spend, limit 10)
    top_ads = sorted(ads, key=lambda x: x["spend"], reverse=True)[:10]
    creatives_html = ""
    for ad in top_ads:
        if ad["spend"] < 1:
            continue
        thumb = f'<img class="ad-thumb" src="{ad["thumbnail"]}" alt="" loading="lazy">' if ad["thumbnail"] else '<div class="ad-thumb-placeholder"></div>'
        link_btn = f'<a class="ad-link" href="{ad["permalink"]}" target="_blank" rel="noopener">Ver publicação ↗</a>' if ad.get("permalink") else ''
        body_preview = esc(ad.get("body", "")[:120])
        creatives_html += f"""
        <div class="ad-card">
            <div class="ad-top">
                {thumb}
                <div class="ad-info">
                    <div class="ad-name">{esc(ad['name'][:50])}</div>
                    <div class="ad-meta">R$ {ad['spend']:.2f} · {ad['clicks']} cliques · {ad['conversions']} conv · CTR {ad['ctr']:.2f}%</div>
                    {f'<div class="ad-cpl">Custo/conv: R$ {ad["cpl"]:.2f}</div>' if ad['cpl'] > 0 else ''}
                    {link_btn}
                </div>
            </div>
            {f'<div class="ad-body">{body_preview}</div>' if body_preview else ''}
        </div>"""

    # Balance section
    bal_color = "#22c55e" if b["remaining"] > 500 else "#f59e0b" if b["remaining"] > 100 else "#ef4444"
    bal_html = ""
    if b["spend_cap"] > 0:
        bal_html = f"""
        <div class="balance-section">
            <div class="bal-row"><span>Limite da conta</span><span>R$ {b['spend_cap']:,.2f}</span></div>
            <div class="bal-row"><span>Gasto total</span><span>R$ {b['amount_spent']:,.2f}</span></div>
            <div class="bal-row highlight"><span>Saldo restante</span><span style="color:{bal_color}">R$ {b['remaining']:,.2f}</span></div>
            <div class="bal-bar"><div class="bal-fill" style="width:{min(b['pct_used'],100):.0f}%;background:{bal_color}"></div></div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Seven · {nome}</title>
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#F7F8FA;color:#184341;font-family:'Montserrat',system-ui,sans-serif}}

.topbar{{background:#184341;display:flex;justify-content:space-between;align-items:center;padding:0 32px;height:60px;position:sticky;top:0;z-index:10}}
.logo{{display:flex;align-items:center;gap:8px;text-decoration:none}}
.logo svg{{width:28px;height:28px}}
.logo-text{{font-size:20px;font-weight:800;background:linear-gradient(135deg,#38bdf8,#2dd4bf);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
.topbar-right{{display:flex;align-items:center;gap:12px}}
.live-dot{{width:8px;height:8px;border-radius:50%;background:#22c55e;animation:blink 2s infinite}}
@keyframes blink{{0%,100%{{opacity:1}}50%{{opacity:.3}}}}
.topbar-label{{font-size:12px;color:rgba(255,255,255,.6)}}

.container{{max-width:1100px;margin:0 auto;padding:32px 24px}}
.hero h1{{font-size:26px;font-weight:800;margin-bottom:4px}}
.hero .sub{{font-size:14px;color:#7a7a7a;margin-bottom:24px}}
.hero .info{{font-size:12px;color:#999;margin-bottom:24px}}

.kpis{{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:12px;margin-bottom:32px}}
.kpi{{background:#fff;border-radius:12px;padding:16px;text-align:center;box-shadow:0 1px 3px rgba(0,0,0,.06)}}
.kpi-v{{display:block;font-size:18px;font-weight:800;color:#184341}}
.kpi-l{{display:block;font-size:11px;color:#999;margin-top:4px;font-weight:600}}

.section-header{{font-size:16px;font-weight:700;margin:32px 0 16px;padding-bottom:8px;border-bottom:2px solid #e8e8e8}}

.camp-table{{width:100%;border-collapse:collapse;font-size:12px;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.06)}}
.camp-table th{{background:#184341;color:#fff;padding:10px 12px;text-align:left;font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.03em}}
.camp-table td{{padding:10px 12px;border-bottom:1px solid #f0f0f0}}
.camp-table tr:last-child td{{border-bottom:none}}
.camp-table tr:hover td{{background:#f8fafa}}
.dot{{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:6px}}
.dot.active{{background:#22c55e}}
.dot.paused{{background:#d1d5db}}
.obj-tag{{font-size:10px;font-weight:700;color:#fff;padding:2px 8px;border-radius:8px}}

.chart-container{{background:#fff;border-radius:12px;padding:20px;box-shadow:0 1px 3px rgba(0,0,0,.06);margin-bottom:32px}}
.chart-container canvas{{max-height:280px}}

.creatives-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px}}
.ad-card{{background:#fff;border-radius:12px;padding:16px;box-shadow:0 1px 3px rgba(0,0,0,.06)}}
.ad-top{{display:flex;gap:12px;align-items:flex-start}}
.ad-thumb{{width:80px;height:80px;border-radius:10px;object-fit:cover;flex-shrink:0;background:#eee}}
.ad-thumb-placeholder{{width:80px;height:80px;border-radius:10px;background:#eee;flex-shrink:0}}
.ad-info{{flex:1;min-width:0}}
.ad-name{{font-size:12px;font-weight:700;margin-bottom:4px;word-break:break-word}}
.ad-meta{{font-size:11px;color:#7a7a7a;margin-bottom:2px}}
.ad-cpl{{font-size:11px;font-weight:700;color:#22c55e;margin-bottom:4px}}
.ad-link{{display:inline-block;margin-top:4px;font-size:11px;font-weight:600;color:#00A19A;text-decoration:none;padding:3px 10px;border:1px solid #00A19A;border-radius:6px;transition:all .15s}}
.ad-link:hover{{background:#00A19A;color:#fff}}
.ad-body{{font-size:11px;color:#666;margin-top:10px;line-height:1.5;padding-top:10px;border-top:1px solid #f0f0f0}}

.balance-section{{background:#fff;border-radius:12px;padding:20px;box-shadow:0 1px 3px rgba(0,0,0,.06);margin-bottom:32px;max-width:400px}}
.bal-row{{display:flex;justify-content:space-between;font-size:13px;margin-bottom:6px}}
.bal-row.highlight{{font-weight:700;font-size:14px;margin-top:8px}}
.bal-bar{{height:6px;background:#e5e7eb;border-radius:4px;margin-top:10px;overflow:hidden}}
.bal-fill{{height:100%;border-radius:4px;transition:width .5s}}

.footer{{text-align:center;padding:32px;font-size:11px;color:#bbb}}

.table-wrap{{overflow-x:auto;margin-bottom:32px}}

@media(max-width:768px){{
    .kpis{{grid-template-columns:repeat(2,1fr)}}
    .creatives-grid{{grid-template-columns:1fr}}
    .camp-table{{font-size:11px}}
    .camp-table th,.camp-table td{{padding:8px 6px}}
    .ad-thumb{{width:100%;height:160px;border-radius:8px}}
    .ad-top{{flex-direction:column}}
}}
</style>
</head>
<body>

<div class="topbar">
    <div class="logo">
        <svg viewBox="0 0 24 24" fill="none"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" fill="url(#lg)"/><defs><linearGradient id="lg" x1="3" y1="2" x2="21" y2="22"><stop stop-color="#38bdf8"/><stop offset="1" stop-color="#2dd4bf"/></linearGradient></defs></svg>
        <span class="logo-text">seven</span>
    </div>
    <div class="topbar-right">
        <div class="live-dot"></div>
        <span class="topbar-label">Atualizado {now}</span>
    </div>
</div>

<div class="container">
    <div class="hero">
        <h1>{nome}</h1>
        <p class="sub">{subtitle + ' · ' if subtitle else ''}Dashboard de Performance Meta Ads</p>
        <p class="info">{s['total_camps']} campanhas ({s['active']} ativas) · Conta: {p.get('account_name', '')}</p>
    </div>

    <div class="kpis">{kpi_html}</div>

    {bal_html}

    <h3 class="section-header">Últimos 7 dias</h3>
    <div class="chart-container">
        <canvas id="dailyChart"></canvas>
    </div>

    <h3 class="section-header">Campanhas</h3>
    <div class="table-wrap">
        <table class="camp-table">
            <thead><tr>
                <th>Campanha</th><th>Objetivo</th><th>Gasto</th><th>Alcance</th><th>Cliques</th><th>CTR</th><th>Conv</th><th>Custo/Conv</th>
            </tr></thead>
            <tbody>{camp_rows_html}</tbody>
        </table>
    </div>

    <h3 class="section-header">Top Criativos</h3>
    <div class="creatives-grid">{creatives_html}</div>

    <div class="footer">
        <div>seven midas · marketing digital · atualizado em {now}</div>
    </div>
</div>

<script>
new Chart(document.getElementById('dailyChart'),{{
    type:'bar',
    data:{{
        labels:{chart_labels},
        datasets:[
            {{label:'Gasto (R$)',data:{chart_spend},backgroundColor:'rgba(0,161,154,0.2)',borderColor:'#00A19A',borderWidth:2,borderRadius:6,order:2}},
            {{label:'Cliques',data:{chart_clicks},type:'line',borderColor:'#1D71B8',backgroundColor:'transparent',borderWidth:2,pointRadius:3,tension:.3,yAxisID:'y1',order:1}},
            {{label:'Conversões',data:{chart_convs},type:'line',borderColor:'#22c55e',backgroundColor:'transparent',borderWidth:2,pointRadius:3,tension:.3,yAxisID:'y1',order:0}}
        ]
    }},
    options:{{
        responsive:true,
        interaction:{{mode:'index',intersect:false}},
        plugins:{{legend:{{position:'bottom',labels:{{font:{{family:'Montserrat',size:11}}}}}}}},
        scales:{{
            y:{{beginAtZero:true,grid:{{color:'#f0f0f0'}},ticks:{{font:{{family:'Montserrat',size:11}},callback:v=>'R$ '+v}}}},
            y1:{{position:'right',beginAtZero:true,grid:{{display:false}},ticks:{{font:{{family:'Montserrat',size:11}}}}}},
            x:{{grid:{{display:false}},ticks:{{font:{{family:'Montserrat',size:11}}}}}}
        }}
    }}
}});
</script>

</body>
</html>"""
    return html
