"""
Dashboard de Inauguração — Cuiabá & Parauapebas
Dashboards separados, funil por jornada do paciente, criativos com copy.
"""

import json
import os
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN = os.environ["META_ACCESS_TOKEN"]
API_VERSION = "v21.0"
API_BASE = f"https://graph.facebook.com/{API_VERSION}"

UNITS = {
    "cuiaba": {"nome": "Cuiabá", "estado": "MT", "account_id": "934816888951624"},
    "parauapebas": {"nome": "Parauapebas", "estado": "PA", "account_id": "2428950724211358"},
}


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


def classify_funnel_by_journey(campaign_name, cta_type=""):
    """
    Classificação por jornada do paciente (inauguração):
    - TOPO: trafego-perfil (awareness, descoberta)
    - MEIO: vendas WPP público frio (consideração, conversa inicial)
    - FUNDO: vendas WPP remarketing (conversão, público quente)
    """
    name = campaign_name.lower()
    if "trafego" in name or "perfil" in name or cta_type == "VIEW_INSTAGRAM_PROFILE":
        return "topo"
    if any(k in name for k in ["rmk", "remarketing", "retargeting"]):
        return "fundo"
    if any(k in name for k in ["vendas", "wpp", "whatsapp", "mensag"]):
        return "meio"
    return "meio"


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
        "fields": "name,status,effective_status,campaign_id,adset_id,creative{id,title,body,call_to_action_type,object_story_spec,asset_feed_spec,thumbnail_url}",
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

    adsets = meta_get(f"act_{account_id}/adsets", {
        "fields": "name,status,effective_status,campaign_id,daily_budget,targeting,optimization_goal,promoted_object",
        "limit": 50,
    })
    if isinstance(adsets, dict): adsets = []

    daily = meta_get(f"act_{account_id}/insights", {
        "fields": "spend,impressions,clicks,ctr,actions,date_start",
        "date_preset": "last_7d",
        "level": "account",
        "time_increment": "1",
    })
    if isinstance(daily, dict): daily = []

    total = meta_get(f"act_{account_id}/insights", {
        "fields": "spend,impressions,clicks,ctr,cpc,reach,frequency,actions",
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
        "adsets": adsets,
        "daily": daily,
        "total": total[0] if total else {},
    }


def get_ad_creative_info(ad):
    """Extrai copy, título, descrição e thumbnail do anúncio."""
    creative = ad.get("creative", {})
    body = creative.get("body", "")
    title = creative.get("title", "")
    thumbnail = creative.get("thumbnail_url", "")
    cta = creative.get("call_to_action_type", "")
    description = ""

    oss = creative.get("object_story_spec", {})
    if oss:
        vd = oss.get("video_data", {})
        if vd:
            body = body or vd.get("message", "")
            title = title or vd.get("title", "")
            description = vd.get("link_description", "")
        ld = oss.get("link_data", {})
        if ld:
            body = body or ld.get("message", "")
            title = title or ld.get("name", "")
            description = description or ld.get("description", "")

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

    return {
        "body": body,
        "title": title,
        "description": description,
        "thumbnail": thumbnail,
        "cta": cta,
    }


def build_targeting_info(data):
    """Extrai info de segmentação dos adsets, agrupado por campanha."""
    camps_map = {c["id"]: c for c in data["campaigns"]}
    result = []
    for adset in data.get("adsets", []):
        cid = adset.get("campaign_id", "")
        camp = camps_map.get(cid, {})
        cname = camp.get("name", "")
        stage = classify_funnel_by_journey(cname)
        t = adset.get("targeting", {})
        geo = t.get("geo_locations", {})

        cities = []
        for c in geo.get("cities", []):
            r = c.get("radius", "")
            cities.append(f"{c.get('name', '')} ({r}km)" if r else c.get("name", ""))
        for cl in geo.get("custom_locations", []):
            cities.append(f"CEP/Coord ({cl.get('radius', '')}km)")

        interests = []
        for flex in t.get("flexible_spec", []):
            for key, vals in flex.items():
                for v in vals:
                    if isinstance(v, dict):
                        interests.append(v.get("name", ""))
                    elif isinstance(v, str):
                        interests.append(v)

        custom_audiences = [ca.get("name", "") for ca in t.get("custom_audiences", [])]
        excluded_audiences = [ca.get("name", "") for ca in t.get("excluded_custom_audiences", [])]

        result.append({
            "adset_name": adset.get("name", ""),
            "campaign_name": cname,
            "stage": stage,
            "status": adset.get("effective_status", ""),
            "optimization": adset.get("optimization_goal", ""),
            "age_min": t.get("age_min", ""),
            "age_max": t.get("age_max", ""),
            "genders": t.get("genders"),
            "cities": cities,
            "interests": interests,
            "custom_audiences": custom_audiences,
            "excluded_audiences": excluded_audiences,
            "daily_budget": int(adset.get("daily_budget", 0)) / 100,
        })
    return result


def process(data):
    camps_map = {c["id"]: c for c in data["campaigns"]}
    ads_map = {}
    for ad in data["ads"]:
        ads_map[ad["id"]] = ad

    # Build ad creative lookup by ad name + campaign_id
    ad_creative_lookup = {}
    for ad in data["ads"]:
        key = (ad["name"], ad.get("campaign_id", ""))
        if key not in ad_creative_lookup:
            ad_creative_lookup[key] = get_ad_creative_info(ad)
        # Also index by just name for fallback
        if ad["name"] not in ad_creative_lookup:
            ad_creative_lookup[ad["name"]] = get_ad_creative_info(ad)

    # Process campaign-level data
    funnel = {"topo": [], "meio": [], "fundo": []}
    totals = {k: {"spend": 0, "impressions": 0, "reach": 0, "clicks": 0, "leads": 0, "conversations": 0}
              for k in funnel}

    for row in data["camp_insights"]:
        cid = row.get("campaign_id", "")
        cname = row.get("campaign_name", "")
        camp = camps_map.get(cid, {})
        status = camp.get("effective_status", "UNKNOWN")
        stage = classify_funnel_by_journey(cname)

        spend = float(row.get("spend", 0))
        impressions = int(row.get("impressions", 0))
        reach = int(row.get("reach", 0))
        clicks = int(row.get("clicks", 0))
        ctr = float(row.get("ctr", 0))
        frequency = float(row.get("frequency", 0))

        conversations = extract_action(row.get("actions"), "onsite_conversion.messaging_conversation_started_7d")
        link_clicks = extract_action(row.get("actions"), "link_click")
        video_views = extract_action(row.get("actions"), "video_view")
        post_engagement = extract_action(row.get("actions"), "post_engagement")
        depth2 = extract_action(row.get("actions"), "onsite_conversion.messaging_user_depth_2_message_send")
        depth3 = extract_action(row.get("actions"), "onsite_conversion.messaging_user_depth_3_message_send")
        leads = conversations if conversations > 0 else extract_action(row.get("actions"), "lead")

        daily_budget = int(camp.get("daily_budget", 0)) / 100

        funnel[stage].append({
            "id": cid, "name": cname, "status": status,
            "spend": spend, "impressions": impressions, "reach": reach, "clicks": clicks,
            "ctr": ctr, "frequency": frequency, "leads": leads, "conversations": conversations,
            "cpl": spend / leads if leads > 0 else 0,
            "link_clicks": link_clicks, "video_views": video_views,
            "post_engagement": post_engagement, "depth2": depth2, "depth3": depth3,
            "daily_budget": daily_budget,
        })
        for k in ["spend", "impressions", "reach", "clicks", "leads", "conversations"]:
            totals[stage][k] += locals()[k] if k not in ("leads", "conversations") else eval(k)

    # Process ad-level data (creatives)
    ad_data = {"topo": [], "meio": [], "fundo": []}
    for row in data["ad_insights"]:
        ad_name = row.get("ad_name", "")
        cname = row.get("campaign_name", "")
        cid = row.get("campaign_id", "")
        stage = classify_funnel_by_journey(cname)

        creative = ad_creative_lookup.get((ad_name, cid)) or ad_creative_lookup.get(ad_name) or {}

        spend = float(row.get("spend", 0))
        conversations = extract_action(row.get("actions"), "onsite_conversion.messaging_conversation_started_7d")
        link_clicks_ad = extract_action(row.get("actions"), "link_click")

        ad_data[stage].append({
            "name": ad_name,
            "campaign": cname,
            "spend": spend,
            "impressions": int(row.get("impressions", 0)),
            "reach": int(row.get("reach", 0)),
            "clicks": int(row.get("clicks", 0)),
            "ctr": float(row.get("ctr", 0)),
            "conversations": conversations,
            "link_clicks": link_clicks_ad,
            "cpl": spend / conversations if conversations > 0 else 0,
            "body": creative.get("body", ""),
            "title": creative.get("title", ""),
            "description": creative.get("description", ""),
            "thumbnail": creative.get("thumbnail", ""),
            "cta": creative.get("cta", ""),
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

    # Balance
    info = data["account_info"]
    spend_cap = int(info.get("spend_cap", 0)) / 100
    amount_spent = int(info.get("amount_spent", 0)) / 100
    balance = int(info.get("balance", 0)) / 100
    remaining = (spend_cap - amount_spent) if spend_cap > 0 else balance

    total_row = data["total"]
    total_spend = float(total_row.get("spend", 0))
    total_reach = int(total_row.get("reach", 0))
    total_clicks = int(total_row.get("clicks", 0))
    total_impressions = int(total_row.get("impressions", 0))
    total_ctr = float(total_row.get("ctr", 0))
    total_convs = sum(t["conversations"] for t in totals.values())
    total_leads = sum(t["leads"] for t in totals.values())
    total_cpl = total_spend / total_leads if total_leads > 0 else 0

    active_camps = [c for c in data["campaigns"] if c.get("effective_status") == "ACTIVE"]
    # Budget: CBO = campaign level, ABO = sum adset budgets
    daily_budget_total = 0
    for camp in active_camps:
        camp_budget = int(camp.get("daily_budget", 0)) / 100
        if camp_budget > 0:
            # CBO: budget is on the campaign
            daily_budget_total += camp_budget
        else:
            # ABO: sum adset budgets for this campaign
            for adset in data.get("adsets", []):
                if adset.get("campaign_id") == camp["id"] and adset.get("effective_status") == "ACTIVE":
                    daily_budget_total += int(adset.get("daily_budget", 0)) / 100
    avg_daily = total_spend / max(len(daily_chart), 1) if daily_chart else daily_budget_total
    days_left = remaining / avg_daily if avg_daily > 0 else 0

    return {
        "funnel": funnel, "totals": totals,
        "ad_data": ad_data, "daily_chart": daily_chart,
        "balance": {
            "remaining": remaining, "spend_cap": spend_cap, "amount_spent": amount_spent,
            "daily_budget": daily_budget_total, "days_left": days_left,
            "pct_used": (amount_spent / spend_cap * 100) if spend_cap > 0 else 0,
        },
        "summary": {
            "spend": total_spend, "reach": total_reach, "clicks": total_clicks,
            "impressions": total_impressions, "ctr": total_ctr, "leads": total_leads,
            "conversations": total_convs, "cpl": total_cpl,
            "active": len(active_camps), "total_camps": len(data["campaigns"]),
        },
        "account_name": info.get("name", ""),
        "targeting": build_targeting_info(data),
    }


def esc(text):
    """Escape HTML."""
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("\n", "<br>")


def _build_analysis_html(p):
    """Análise de campanhas: diagnóstico, winners, waste, ações."""
    ad_data = p["ad_data"]
    totals = p["totals"]
    s = p["summary"]

    # ── HEALTH CHECK por etapa ──
    health_html = ""

    # TOPO
    t = totals["topo"]
    if t["spend"] > 0:
        cpv = t["spend"] / t["clicks"] if t["clicks"] > 0 else 0
        cpm = (t["spend"] / t["impressions"] * 1000) if t["impressions"] > 0 else 0
        ctr_topo = (t["clicks"] / t["impressions"] * 100) if t["impressions"] > 0 else 0
        cpv_status = "good" if cpv < 0.60 else "ok" if cpv < 1.00 else "bad"
        ctr_status = "good" if ctr_topo > 3 else "ok" if ctr_topo > 1.5 else "bad"
        health_html += f"""
        <div class="health-card" style="border-left-color:#1D71B8">
            <h4>Topo de Funil — Tráfego para Perfil</h4>
            <table class="health-table">
                <tr><td>Custo por Visita</td><td>R$ {cpv:.2f}</td><td>{'< R$ 0,60' if cpv_status=='good' else '< R$ 1,00' if cpv_status=='ok' else '> R$ 1,00'}</td><td class="{cpv_status}">{'Excelente' if cpv_status=='good' else 'Aceitável' if cpv_status=='ok' else 'Alto'}</td></tr>
                <tr><td>CTR</td><td>{ctr_topo:.2f}%</td><td>> 3%</td><td class="{ctr_status}">{'Excelente' if ctr_status=='good' else 'Aceitável' if ctr_status=='ok' else 'Baixo'}</td></tr>
                <tr><td>CPM</td><td>R$ {cpm:.2f}</td><td>Referência</td><td class="ok">—</td></tr>
                <tr><td>Alcance</td><td>{t['reach']:,}</td><td>—</td><td class="ok">—</td></tr>
            </table>
        </div>"""

    # MEIO
    t = totals["meio"]
    if t["spend"] > 0:
        cpl = t["spend"] / t["conversations"] if t["conversations"] > 0 else 0
        conv_rate = (t["conversations"] / t["clicks"] * 100) if t["clicks"] > 0 else 0
        ctr_meio = (t["clicks"] / t["impressions"] * 100) if t["impressions"] > 0 else 0
        cpl_status = "good" if cpl < 5 else "ok" if cpl < 10 else "bad"
        cr_status = "good" if conv_rate > 25 else "ok" if conv_rate > 15 else "bad"
        health_html += f"""
        <div class="health-card" style="border-left-color:#00A19A">
            <h4>Meio de Funil — Conversas WPP (Público Frio)</h4>
            <table class="health-table">
                <tr><td>Custo por Conversa</td><td>R$ {cpl:.2f}</td><td>{'< R$ 5' if cpl_status=='good' else '< R$ 10' if cpl_status=='ok' else '> R$ 10'}</td><td class="{cpl_status}">{'Excelente' if cpl_status=='good' else 'Aceitável' if cpl_status=='ok' else 'Alto'}</td></tr>
                <tr><td>Taxa de Conversão</td><td>{conv_rate:.1f}%</td><td>> 25%</td><td class="{cr_status}">{'Excelente' if cr_status=='good' else 'Aceitável' if cr_status=='ok' else 'Baixa'}</td></tr>
                <tr><td>CTR</td><td>{ctr_meio:.2f}%</td><td>> 1.5%</td><td class="{'good' if ctr_meio > 1.5 else 'ok'}">{'Bom' if ctr_meio > 1.5 else 'Aceitável'}</td></tr>
                <tr><td>Conversas</td><td>{t['conversations']}</td><td>—</td><td class="good">—</td></tr>
            </table>
        </div>"""

    # FUNDO
    t = totals["fundo"]
    if t["spend"] > 0:
        cpl_f = t["spend"] / t["conversations"] if t["conversations"] > 0 else 0
        cpl_f_status = "good" if cpl_f < 10 else "ok" if cpl_f < 20 else "bad"
        health_html += f"""
        <div class="health-card" style="border-left-color:#22c55e">
            <h4>Fundo de Funil — Remarketing WPP</h4>
            <table class="health-table">
                <tr><td>Custo por Conversa</td><td>{'R$ '+f'{cpl_f:.2f}' if t['conversations']>0 else '—'}</td><td>< R$ 10</td><td class="{cpl_f_status if t['conversations']>0 else 'ok'}">{'Excelente' if cpl_f_status=='good' and t['conversations']>0 else 'Aceitável' if cpl_f_status=='ok' and t['conversations']>0 else 'Monitorar' if t['conversations']>0 else 'Em ramp-up'}</td></tr>
                <tr><td>Conversas</td><td>{t['conversations']}</td><td>—</td><td class="ok">—</td></tr>
                <tr><td>Alcance RMK</td><td>{t['reach']:,}</td><td>—</td><td class="ok">—</td></tr>
            </table>
        </div>"""

    # ── WINNERS (meio + fundo) ──
    all_conv_ads = [a for a in ad_data["meio"] + ad_data["fundo"] if a["conversations"] > 0]
    all_conv_ads.sort(key=lambda x: x["cpl"])
    winners_html = ""
    for a in all_conv_ads[:5]:
        winners_html += f"""
        <tr>
            <td>{esc(a['name'])}</td>
            <td>R$ {a['spend']:.2f}</td>
            <td>{a['conversations']}</td>
            <td><strong style="color:#22c55e">R$ {a['cpl']:.2f}</strong></td>
            <td>{a['ctr']:.2f}%</td>
            <td>Escalar</td>
        </tr>"""

    # ── WASTE (ads com gasto sem conversão no meio/fundo) ──
    waste_ads = [a for a in ad_data["meio"] + ad_data["fundo"] if a["conversations"] == 0 and a["spend"] > 2]
    waste_ads.sort(key=lambda x: x["spend"], reverse=True)
    total_waste = sum(a["spend"] for a in waste_ads)
    waste_html = ""
    for a in waste_ads[:5]:
        waste_html += f"""
        <tr>
            <td>{esc(a['name'])}</td>
            <td>R$ {a['spend']:.2f}</td>
            <td>{a['reach']:,}</td>
            <td>{a['clicks']}</td>
            <td>0</td>
            <td style="color:#ef4444">Pausar/Revisar</td>
        </tr>"""

    # ── TOPO winners ──
    topo_ads = sorted(ad_data["topo"], key=lambda x: x["link_clicks"], reverse=True)
    topo_winners = ""
    for a in topo_ads[:5]:
        if a["link_clicks"] > 0:
            cpv = a["spend"] / a["link_clicks"]
            topo_winners += f"""
            <tr>
                <td>{esc(a['name'])}</td>
                <td>R$ {a['spend']:.2f}</td>
                <td>{a['reach']:,}</td>
                <td><strong style="color:#1D71B8">{a['link_clicks']}</strong></td>
                <td>R$ {cpv:.2f}</td>
            </tr>"""

    # ── ACTION PLAN ──
    actions_immediate = []
    for a in waste_ads[:3]:
        actions_immediate.append(f"Pausar criativo <strong>{esc(a['name'])}</strong> — R$ {a['spend']:.2f} gasto sem conversão")
    if all_conv_ads:
        best = all_conv_ads[0]
        actions_immediate.append(f"Escalar criativo <strong>{esc(best['name'])}</strong> — melhor CPL R$ {best['cpl']:.2f}")

    actions_week = []
    actions_week.append("Testar novos ângulos de copy baseados nos winners (sintomas + resultado)")
    actions_week.append("Avaliar frequência dos criativos e rotacionar se necessário")
    if totals["fundo"]["spend"] < 50:
        actions_week.append("Aguardar maturação da campanha de remarketing (ainda em ramp-up)")

    return f"""
        <h3>Análise de Performance por Campanha</h3>
        <div class="health-grid">{health_html}</div>

        <h3>Top Criativos — Topo de Funil (Visitas ao Perfil)</h3>
        <table class="analysis-table">
            <thead><tr><th>Criativo</th><th>Gasto</th><th>Alcance</th><th>Visitas</th><th>Custo/Visita</th></tr></thead>
            <tbody>{topo_winners if topo_winners else '<tr><td colspan="5" style="text-align:center;color:#5a5a5a">Sem dados suficientes</td></tr>'}</tbody>
        </table>

        <h3>Top Criativos — Conversas WPP (Menor CPL)</h3>
        <table class="analysis-table">
            <thead><tr><th>Criativo</th><th>Gasto</th><th>Conversas</th><th>CPL</th><th>CTR</th><th>Ação</th></tr></thead>
            <tbody>{winners_html if winners_html else '<tr><td colspan="6" style="text-align:center;color:#5a5a5a">Sem conversas ainda</td></tr>'}</tbody>
        </table>

        {'<h3>Desperdício Detectado</h3><p>Criativos com gasto mas <strong>zero conversas</strong> nas campanhas de WhatsApp — total de <strong style="color:#ef4444">R$ '+f'{total_waste:.2f}'+'</strong> ('+ f'{(total_waste/s["spend"]*100):.0f}' +'% do investimento):</p><table class="analysis-table"><thead><tr><th>Criativo</th><th>Gasto</th><th>Alcance</th><th>Cliques</th><th>Conversas</th><th>Ação</th></tr></thead><tbody>'+waste_html+'</tbody></table>' if waste_html else ''}

        <h3>Plano de Ação</h3>
        <div class="action-plan">
            <div class="action-group">
                <h4>Imediato</h4>
                <ul>{''.join(f'<li>{a}</li>' for a in actions_immediate)}</ul>
            </div>
            <div class="action-group">
                <h4>Esta Semana</h4>
                <ul>{''.join(f'<li>{a}</li>' for a in actions_week)}</ul>
            </div>
        </div>
    """


def _build_report_html(unit, p, now):
    s = p["summary"]
    b = p["balance"]
    totals = p["totals"]
    targeting = p["targeting"]

    stage_names = {"topo": "Topo de Funil", "meio": "Meio de Funil", "fundo": "Fundo de Funil"}
    stage_colors = {"topo": "#1D71B8", "meio": "#00A19A", "fundo": "#22c55e"}

    # Build targeting cards
    targeting_html = ""
    for stage_key in ["topo", "meio", "fundo"]:
        stage_targets = [t for t in targeting if t["stage"] == stage_key]
        if not stage_targets:
            continue
        cards = ""
        for t in stage_targets:
            gender_text = "Todos" if not t["genders"] or t["genders"] == [0] else "Masculino" if t["genders"] == [1] else "Feminino" if t["genders"] == [2] else str(t["genders"])
            opt_map = {"CONVERSATIONS": "Conversas (WhatsApp)", "PROFILE_VISIT": "Visitas ao Perfil"}
            opt_text = opt_map.get(t["optimization"], t["optimization"])

            loc_html = ", ".join(t["cities"]) if t["cities"] else "Por CEPs segmentados"
            interests_html = ""
            if t["interests"]:
                tags = "".join(f'<span class="tc-tag">{esc(i)}</span>' for i in t["interests"])
                interests_html = f'<div class="tc-label">Interesses</div><div class="tc-tags">{tags}</div>'
            audiences_html = ""
            if t["custom_audiences"]:
                tags = "".join(f'<span class="tc-tag">{esc(a)}</span>' for a in t["custom_audiences"])
                audiences_html = f'<div class="tc-label">Públicos Personalizados</div><div class="tc-tags">{tags}</div>'

            cards += f"""
            <div class="targeting-card" style="--tc:{stage_colors[stage_key]}">
                <h4>{esc(t['adset_name'][:60])}</h4>
                <div class="tc-label">Otimização</div>
                <div class="tc-value">{opt_text}</div>
                <div class="tc-label">Idade</div>
                <div class="tc-value">{t['age_min']} - {t['age_max']} anos</div>
                <div class="tc-label">Gênero</div>
                <div class="tc-value">{gender_text}</div>
                <div class="tc-label">Localização</div>
                <div class="tc-value">{esc(loc_html)}</div>
                {interests_html}
                {audiences_html}
                {'<div class="tc-label">Budget</div><div class="tc-value">R$ '+f"{t['daily_budget']:.0f}"+'/dia</div>' if t['daily_budget'] > 0 else ''}
            </div>"""

        targeting_html += f"""
        <h3>{stage_names[stage_key]}</h3>
        <div class="targeting-grid">{cards}</div>"""

    t_topo = totals["topo"]
    t_meio = totals["meio"]
    t_fundo = totals["fundo"]
    cost_per_visit = t_topo["spend"] / t_topo["clicks"] if t_topo["clicks"] > 0 else 0
    cpl_meio = t_meio["spend"] / t_meio["conversations"] if t_meio["conversations"] > 0 else 0

    return f"""
    <div class="report-card">
        <h2>Relatório de Tráfego — Inauguração {unit['nome']}</h2>

        <div class="greeting">
            <p>Olá! Segue o relatório atualizado das campanhas de inauguração da unidade <strong>Doutor DM2 {unit['nome']}</strong>.</p>
            <p>As campanhas foram estruturadas em <strong>etapas distintas do funil</strong>, cada uma com objetivo, público e otimização específicos. Abaixo explico a estratégia e os resultados de cada etapa.</p>
        </div>

        <h3>Por que campanhas separadas?</h3>
        <p>Em uma inauguração, precisamos trabalhar o funil completo de forma estratégica. Cada campanha tem um papel específico:</p>
        <ul>
            <li><strong>Topo de Funil (Tráfego para Perfil)</strong> — O objetivo aqui é <strong>awareness</strong>. A cidade ainda não conhece a Doutor DM2, então precisamos gerar visitas ao perfil do Instagram para que as pessoas descubram a clínica, vejam o conteúdo e comecem a seguir. A otimização é para <strong>visitas ao perfil</strong>, não para conversas.</li>
            <li><strong>Meio de Funil (Vendas WPP — Público Frio)</strong> — Aqui o objetivo muda para <strong>iniciar conversas no WhatsApp</strong>. Atingimos pessoas que ainda não nos conhecem (público frio segmentado por CEP e interesses), mas agora com o CTA direto para o WhatsApp. É a etapa de <strong>consideração</strong> — a pessoa conhece a proposta e tira dúvidas.</li>
            <li><strong>Fundo de Funil (Remarketing WPP)</strong> — Essa campanha atinge <strong>apenas quem já interagiu</strong> com nosso conteúdo: envolvimento no Instagram/Facebook nos últimos 365 dias e quem assistiu pelo menos 25% dos vídeos. É o <strong>público quente</strong> sendo direcionado para agendar a consulta.</li>
        </ul>

        <h3>Resultados Gerais</h3>
        <p>Desde o início das campanhas, investimos <strong>R$ {s['spend']:,.2f}</strong> com os seguintes resultados:</p>
        <ul>
            <li><strong>Alcance total:</strong> {s['reach']:,} pessoas</li>
            <li><strong>Impressões:</strong> {s['impressions']:,}</li>
            <li><strong>Visitas ao perfil (Topo):</strong> {t_topo['clicks']:,} — Custo por visita: {'R$ '+f'{cost_per_visit:.2f}' if cost_per_visit > 0 else '—'}</li>
            <li><strong>Conversas no WhatsApp (Meio):</strong> {t_meio['conversations']} — Custo por conversa: {'R$ '+f'{cpl_meio:.2f}' if cpl_meio > 0 else '—'}</li>
            <li><strong>Conversas Remarketing (Fundo):</strong> {t_fundo['conversations']} conversas de público quente</li>
            <li><strong>Total de conversas:</strong> {s['conversations']}</li>
        </ul>

        <h3>Saldo e Projeção</h3>
        <p>O saldo atual da conta é de <strong style="color:{('#22c55e' if b['remaining']>500 else '#f59e0b' if b['remaining']>100 else '#ef4444')}">R$ {b['remaining']:,.2f}</strong>.
        {'Com o budget diário atual de R$ '+f"{b['daily_budget']:,.0f}"+', estimamos aproximadamente '+f"{b['days_left']:.0f}"+' dias restantes de veiculação.' if b['daily_budget'] > 0 and b['days_left'] < 999 else ''}</p>
        {'<p style="color:#ef4444;font-weight:700">⚠️ ATENÇÃO: saldo crítico — necessário recarregar a conta para manter as campanhas ativas.</p>' if b['remaining'] < 200 else ''}

        {_build_analysis_html(p)}

        <h3>Sobre os Criativos e Abordagens</h3>
        <p>Utilizamos <strong>múltiplos criativos com abordagens diferentes</strong> em cada campanha. Isso é intencional — cada anúncio explora um ângulo de comunicação específico para atingir diferentes perfis de pacientes com diabetes tipo 2:</p>
        <ul>
            <li><strong>Sintomas</strong> — formigamento, cansaço, visão embaçada (identificação com o problema)</li>
            <li><strong>Medicações</strong> — metformina, glicazida, insulina, sulfonilureias (público que já toma remédio)</li>
            <li><strong>Resultado</strong> — "7 em cada 10 em remissão" (prova social e esperança)</li>
            <li><strong>Método</strong> — "controlar não é tratar", protocolo de remissão (diferencial da DM2)</li>
            <li><strong>Urgência</strong> — pré-diabetes, glicada alta, exames alterados (gatilho de ação)</li>
        </ul>
        <p>Cada ângulo atrai um perfil diferente de paciente. A diversidade de criativos nos permite identificar quais mensagens geram mais conversas e otimizar o investimento nos melhores performers.</p>
        <p><strong>Destino das campanhas de WhatsApp:</strong> todas as campanhas de meio e fundo de funil direcionam para o mesmo número de WhatsApp da unidade, onde a equipe de atendimento recebe e qualifica os leads para agendamento.</p>

        <h3>Público e Segmentação por Etapa</h3>
        <p>Cada etapa do funil utiliza segmentação e públicos diferentes para maximizar os resultados:</p>
        {targeting_html}

        <div class="signature">
            <strong>Elainë Cóutinho</strong><br>
            Head de Marketing · Seven Marketing Digital<br>
            {now}
        </div>
    </div>"""


def generate_html(slug, unit, p):
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    s = p["summary"]
    b = p["balance"]
    funnel = p["funnel"]
    totals = p["totals"]
    ad_data = p["ad_data"]
    daily = p["daily_chart"]

    bal_color = "#22c55e" if b["remaining"] > 500 else "#f59e0b" if b["remaining"] > 100 else "#ef4444"

    chart_labels = json.dumps([d["date"] for d in daily])
    chart_spend = json.dumps([d["spend"] for d in daily])
    chart_convs = json.dumps([d["conversations"] for d in daily])
    chart_clicks = json.dumps([d["clicks"] for d in daily])

    # Build stages
    stage_cfg = {
        "topo": {
            "label": "Topo de Funil", "tag": "TOPO", "sublabel": "Awareness & Descoberta",
            "color": "#1D71B8",
            "desc": "Tráfego para perfil — fazer a cidade conhecer a DM2",
        },
        "meio": {
            "label": "Meio de Funil", "tag": "MEIO", "sublabel": "Consideração & Conversas",
            "color": "#00A19A",
            "desc": "Vendas WPP (público frio) — iniciar conversa no WhatsApp",
        },
        "fundo": {
            "label": "Fundo de Funil", "tag": "FUNDO", "sublabel": "Conversão & Remarketing",
            "color": "#22c55e",
            "desc": "Remarketing WPP — converter público quente em agendamentos",
        },
    }

    stages_html = ""
    for sk in ["topo", "meio", "fundo"]:
        cfg = stage_cfg[sk]
        camps = funnel[sk]
        st = totals[sk]
        ads = sorted(ad_data[sk], key=lambda x: x["spend"], reverse=True)

        if not camps:
            stages_html += f"""
            <section class="stage" style="--sc:{cfg['color']}">
                <div class="stage-inner">
                    <div class="stage-top">
                        <span class="tag-pill" style="background:{cfg['color']}">{cfg['tag']}</span>
                        <span class="stage-name">{cfg['label']}</span>
                        <span class="stage-sub">{cfg['sublabel']}</span>
                    </div>
                    <div class="empty">
                        <p>Nenhuma campanha nesta etapa</p>
                        <p class="empty-hint">{cfg['desc']}</p>
                    </div>
                </div>
            </section>"""
            continue

        pct = (st["spend"] / s["spend"] * 100) if s["spend"] > 0 else 0

        # Stage-specific KPIs and metrics
        if sk == "topo":
            cost_per_visit = st["spend"] / st["clicks"] if st["clicks"] > 0 else 0
            stage_kpis_html = f"""
                <div class="stage-kpis">
                    <div class="sk"><span class="sk-v" style="color:{cfg['color']}">R$ {st['spend']:,.2f}</span><span class="sk-l">Investido ({pct:.0f}%)</span></div>
                    <div class="sk"><span class="sk-v">{st['reach']:,}</span><span class="sk-l">Alcance</span></div>
                    <div class="sk"><span class="sk-v">{st['impressions']:,}</span><span class="sk-l">Impressões</span></div>
                    <div class="sk"><span class="sk-v">{st['clicks']:,}</span><span class="sk-l">Visitas ao Perfil</span></div>
                    <div class="sk"><span class="sk-v">{'R$ '+f'{cost_per_visit:.2f}' if cost_per_visit > 0 else '—'}</span><span class="sk-l">Custo/Visita</span></div>
                </div>"""
        elif sk == "meio":
            stage_cpl = st["spend"] / st["conversations"] if st["conversations"] > 0 else 0
            stage_kpis_html = f"""
                <div class="stage-kpis">
                    <div class="sk"><span class="sk-v" style="color:{cfg['color']}">R$ {st['spend']:,.2f}</span><span class="sk-l">Investido ({pct:.0f}%)</span></div>
                    <div class="sk"><span class="sk-v">{st['reach']:,}</span><span class="sk-l">Alcance</span></div>
                    <div class="sk"><span class="sk-v">{st['clicks']:,}</span><span class="sk-l">Cliques</span></div>
                    <div class="sk"><span class="sk-v">{st['conversations']}</span><span class="sk-l">Conversas WPP</span></div>
                    <div class="sk"><span class="sk-v">{'R$ '+f'{stage_cpl:.2f}' if stage_cpl > 0 else '—'}</span><span class="sk-l">Custo/Conversa</span></div>
                </div>"""
        else:  # fundo
            stage_cpl = st["spend"] / st["conversations"] if st["conversations"] > 0 else 0
            stage_kpis_html = f"""
                <div class="stage-kpis">
                    <div class="sk"><span class="sk-v" style="color:{cfg['color']}">R$ {st['spend']:,.2f}</span><span class="sk-l">Investido ({pct:.0f}%)</span></div>
                    <div class="sk"><span class="sk-v">{st['reach']:,}</span><span class="sk-l">Alcance</span></div>
                    <div class="sk"><span class="sk-v">{st['clicks']:,}</span><span class="sk-l">Cliques</span></div>
                    <div class="sk"><span class="sk-v">{st['conversations']}</span><span class="sk-l">Conversas RMK</span></div>
                    <div class="sk"><span class="sk-v">{'R$ '+f'{stage_cpl:.2f}' if stage_cpl > 0 else '—'}</span><span class="sk-l">Custo/Conversa</span></div>
                </div>"""

        # Campaign cards - metrics per stage
        camp_html = ""
        for c in sorted(camps, key=lambda x: x["spend"], reverse=True):
            dot = "active" if c["status"] == "ACTIVE" else "paused"
            if sk == "topo":
                cpv = c["spend"] / c["link_clicks"] if c["link_clicks"] > 0 else 0
                nums_html = f"""
                    <span>R$ {c['spend']:,.2f}</span>
                    <span>{c['reach']:,} alc</span>
                    <span>{c['link_clicks']} visitas</span>
                    <span>{c['ctr']:.2f}% CTR</span>
                    <span>{'R$ '+f'{cpv:.2f}' if cpv>0 else '—'} c/visita</span>"""
            else:
                nums_html = f"""
                    <span>R$ {c['spend']:,.2f}</span>
                    <span>{c['reach']:,} alc</span>
                    <span>{c['clicks']:,} cli</span>
                    <span>{c['conversations']} conv</span>
                    <span>{'R$ '+f'{c["cpl"]:.2f}' if c['cpl']>0 else '—'} cpl</span>"""
            camp_html += f"""
            <div class="camp-row">
                <div class="camp-left">
                    <span class="dot {dot}"></span>
                    <span class="camp-name-text">{esc(c['name'][:55])}</span>
                    {'<span class="budget-tag">R$ '+f"{c['daily_budget']:.0f}/dia</span>" if c['daily_budget']>0 else ""}
                </div>
                <div class="camp-nums">{nums_html}</div>
            </div>"""

        # Ad/Creative cards - ALL ads, no spend filter
        creative_html = ""
        for ad in ads:
            body_preview = esc(ad["body"][:200]) + ("..." if len(ad["body"]) > 200 else "") if ad["body"] else ""
            title_text = esc(ad["title"]) if ad["title"] else ""
            desc_text = esc(ad["description"]) if ad["description"] else ""

            max_spend = max((a["spend"] for a in ads), default=1) or 1
            bar_pct = (ad["spend"] / max_spend * 100) if max_spend > 0 else 0

            # Metrics per funnel stage
            if sk == "topo":
                cpv = ad["spend"] / ad["link_clicks"] if ad["link_clicks"] > 0 else 0
                metrics_html = f"""
                    <div class="am"><span class="am-v">R$ {ad["spend"]:.2f}</span><span class="am-l">Gasto</span></div>
                    <div class="am"><span class="am-v">{ad['reach']:,}</span><span class="am-l">Alcance</span></div>
                    <div class="am"><span class="am-v">{ad['impressions']:,}</span><span class="am-l">Impressões</span></div>
                    <div class="am"><span class="am-v highlight">{ad['link_clicks']}</span><span class="am-l">Visitas Perfil</span></div>
                    <div class="am"><span class="am-v">{ad['ctr']:.2f}%</span><span class="am-l">CTR</span></div>
                    <div class="am"><span class="am-v">{'R$ '+f'{cpv:.2f}' if cpv>0 else '—'}</span><span class="am-l">Custo/Visita</span></div>"""
            else:
                metrics_html = f"""
                    <div class="am"><span class="am-v">R$ {ad["spend"]:.2f}</span><span class="am-l">Gasto</span></div>
                    <div class="am"><span class="am-v">{ad['reach']:,}</span><span class="am-l">Alcance</span></div>
                    <div class="am"><span class="am-v">{ad['clicks']}</span><span class="am-l">Cliques</span></div>
                    <div class="am"><span class="am-v">{ad['ctr']:.2f}%</span><span class="am-l">CTR</span></div>
                    <div class="am"><span class="am-v highlight">{ad['conversations']}</span><span class="am-l">Conversas</span></div>
                    <div class="am"><span class="am-v">{'R$ '+f'{ad["cpl"]:.2f}' if ad["cpl"]>0 else '—'}</span><span class="am-l">CPL</span></div>"""

            creative_html += f"""
            <div class="ad-card">
                <div class="ad-top">
                    {'<img class="ad-thumb" src="'+ad["thumbnail"]+'" alt="" loading="lazy">' if ad["thumbnail"] else '<div class="ad-thumb-placeholder"></div>'}
                    <div class="ad-info">
                        <div class="ad-name">{esc(ad['name'])}</div>
                        {f'<div class="ad-title">{title_text}</div>' if title_text else ''}
                        {f'<div class="ad-desc">{desc_text}</div>' if desc_text else ''}
                    </div>
                </div>
                {f'<div class="ad-body">{body_preview}</div>' if body_preview else ''}
                <div class="ad-metrics">{metrics_html}</div>
                <div class="ad-bar"><div class="ad-bar-fill" style="width:{bar_pct:.0f}%;background:{cfg['color']}"></div></div>
            </div>"""

        stages_html += f"""
        <section class="stage" style="--sc:{cfg['color']}">
            <div class="stage-inner">
                <div class="stage-top">
                    <span class="tag-pill" style="background:{cfg['color']}">{cfg['tag']}</span>
                    <span class="stage-name">{cfg['label']}</span>
                    <span class="stage-sub">{cfg['sublabel']}</span>
                </div>
                <p class="stage-desc">{cfg['desc']}</p>
                {stage_kpis_html}

                <div class="camps-section">
                    <h4 class="sub-header">Campanhas</h4>
                    {camp_html}
                </div>

                <div class="creatives-section">
                    <h4 class="sub-header">Criativos ({len(ads)})</h4>
                    <div class="ad-grid">{creative_html}</div>
                </div>
            </div>
        </section>"""

    # Funnel viz
    t_topo, t_meio, t_fundo = totals["topo"], totals["meio"], totals["fundo"]
    funnel_html = f"""
    <div class="funnel-viz">
        <div class="fv-step" style="width:100%">
            <div class="fv-inner topo {'ghost' if not funnel['topo'] else ''}">
                <span class="fv-tag">TOPO</span>
                <span class="fv-mid">{t_topo['reach']:,} alcance · {t_topo['clicks']:,} visitas ao perfil</span>
                <span class="fv-val">R$ {t_topo['spend']:,.2f}</span>
            </div>
        </div>
        <div class="fv-arrow-line"></div>
        <div class="fv-step" style="width:82%">
            <div class="fv-inner meio {'ghost' if not funnel['meio'] else ''}">
                <span class="fv-tag">MEIO</span>
                <span class="fv-mid">{t_meio['conversations']} conversas WPP · {t_meio['clicks']:,} cli</span>
                <span class="fv-val">R$ {t_meio['spend']:,.2f}</span>
            </div>
        </div>
        <div class="fv-arrow-line"></div>
        <div class="fv-step" style="width:64%">
            <div class="fv-inner fundo {'ghost' if not funnel['fundo'] else ''}">
                <span class="fv-tag">FUNDO</span>
                <span class="fv-mid">{t_fundo['conversations']} conversas RMK · {t_fundo['clicks']:,} cli</span>
                <span class="fv-val">R$ {t_fundo['spend']:,.2f}</span>
            </div>
        </div>
    </div>"""

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Seven · {unit['nome']} — Inauguração</title>
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#F7F8FA;color:#184341;font-family:'Montserrat',system-ui,sans-serif;-webkit-font-smoothing:antialiased;position:relative}}
body::before{{content:'';position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);width:500px;height:500px;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 60'%3E%3Cpath d='M28 4L8 32h18l-2 18 20-28H26l2-18z' fill='%2300A19A' opacity='0.04'/%3E%3Ctext x='52' y='38' font-family='Montserrat,sans-serif' font-weight='800' font-size='32' fill='%2300A19A' opacity='0.04'%3Eseven%3C/text%3E%3C/svg%3E");background-repeat:no-repeat;background-position:center;background-size:contain;pointer-events:none;z-index:0}}

/* ── Topbar ── */
.topbar{{background:#184341;display:flex;justify-content:space-between;align-items:center;padding:0 32px;height:60px;position:sticky;top:0;z-index:10}}
.logo{{display:flex;align-items:center;gap:8px;text-decoration:none}}
.logo svg{{width:30px;height:30px;filter:drop-shadow(0 0 6px rgba(56,189,248,.4))}}
.logo-text{{font-size:22px;font-weight:800;letter-spacing:.02em;background:linear-gradient(135deg,#38bdf8,#2dd4bf);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
.topbar-right{{display:flex;align-items:center;gap:12px}}
.live-dot{{width:8px;height:8px;border-radius:50%;background:#22c55e;animation:blink 2s infinite}}
@keyframes blink{{0%,100%{{opacity:1}}50%{{opacity:.3}}}}
.topbar-label{{font-size:12px;color:rgba(255,255,255,.6)}}
.period-select{{background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.15);color:#fff;font-family:'Montserrat',sans-serif;font-size:12px;font-weight:600;padding:6px 14px;border-radius:8px;cursor:pointer;outline:none;-webkit-appearance:none;appearance:none;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='white' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:right 10px center;padding-right:30px}}
.period-select option{{background:#184341;color:#fff}}
.topbar-badge{{font-size:11px;color:#fff;background:rgba(255,255,255,.12);padding:5px 14px;border-radius:50px;font-weight:600}}

/* ── Hero ── */
.hero{{max-width:1200px;margin:0 auto;padding:32px 32px 24px}}
.hero-row{{display:flex;justify-content:space-between;align-items:flex-end;gap:20px;flex-wrap:wrap}}
.hero h1{{font-size:26px;font-weight:800;color:#184341;letter-spacing:-.02em}}
.hero .city{{color:#00A19A}}
.hero-sub{{font-size:13px;color:#5a5a5a;margin-top:4px}}

/* ── Balance card ── */
.bal{{background:#fff;padding:16px 22px;border-radius:12px;box-shadow:0 2px 12px rgba(0,0,0,.04);text-align:right;min-width:260px}}
.bal-label{{font-size:11px;color:#5a5a5a;text-transform:uppercase;letter-spacing:1px;font-weight:600}}
.bal-val{{font-size:28px;font-weight:800;color:{bal_color};letter-spacing:-.02em;margin-top:2px}}
.bal-det{{font-size:11px;color:#5a5a5a;margin-top:2px}}
.bal-bar{{height:6px;border-radius:3px;background:#eee;margin-top:8px;overflow:hidden}}
.bal-bar-fill{{height:100%;border-radius:3px;background:{bal_color};width:{min(b['pct_used'],100):.0f}%}}

/* ── Tabs ── */
.tabs{{max-width:1200px;margin:0 auto;padding:16px 32px 0;display:flex;gap:8px}}
.tab{{padding:10px 28px;font-size:13px;font-weight:700;color:#5a5a5a;cursor:pointer;border-radius:10px 10px 0 0;transition:all .2s;border:1px solid transparent;border-bottom:none;background:transparent;display:flex;align-items:center;gap:8px}}
.tab:hover{{color:#184341;background:rgba(0,161,154,.04)}}
.tab.active{{color:#fff;background:#184341;border-color:#184341}}
.tab svg{{width:16px;height:16px}}
.tab-divider{{flex:1;border-bottom:2px solid #eee;align-self:flex-end;margin-bottom:0}}
.tab-content{{display:none}}
.tab-content.active{{display:block}}

/* ── Content ── */
.content{{max-width:1200px;margin:0 auto;padding:0 32px 60px}}

/* ── Report ── */
.report-card{{background:#fff;border-radius:12px;box-shadow:0 2px 12px rgba(0,0,0,.04);padding:36px 40px;margin-bottom:24px}}
.report-card h2{{font-size:20px;font-weight:800;color:#184341;margin-bottom:16px}}
.report-card h3{{font-size:15px;font-weight:700;color:#00A19A;margin-top:24px;margin-bottom:10px}}
.report-card p{{font-size:14px;color:#333;line-height:1.8;margin-bottom:12px}}
.report-card ul{{margin:8px 0 16px 20px;font-size:13px;color:#333;line-height:1.8}}
.report-card li{{margin-bottom:4px}}
.report-card .greeting{{font-size:15px;color:#184341;line-height:1.8;margin-bottom:20px}}
.report-card .signature{{margin-top:32px;padding-top:20px;border-top:1px solid #eee;font-size:13px;color:#5a5a5a}}
.report-card .signature strong{{color:#184341;font-size:14px}}
/* ── Analysis tables ── */
.health-grid{{display:flex;flex-direction:column;gap:12px;margin-bottom:8px}}
.health-card{{background:#F7F8FA;border-radius:10px;padding:16px;border-left:4px solid #00A19A}}
.health-card h4{{font-size:13px;font-weight:700;color:#184341;margin-bottom:10px}}
.health-table{{width:100%;font-size:12px;border-collapse:collapse}}
.health-table td{{padding:6px 10px;border-bottom:1px solid #eee}}
.health-table td:first-child{{color:#5a5a5a;font-weight:600}}
.health-table td:nth-child(3){{color:#5a5a5a;font-size:11px}}
.health-table .good{{color:#22c55e;font-weight:700}}
.health-table .ok{{color:#5a5a5a;font-weight:500}}
.health-table .bad{{color:#ef4444;font-weight:700}}

.analysis-table{{width:100%;font-size:12px;border-collapse:collapse;margin-bottom:20px}}
.analysis-table th{{text-align:left;padding:8px 10px;font-size:10px;color:#5a5a5a;text-transform:uppercase;letter-spacing:.5px;font-weight:700;border-bottom:2px solid #eee}}
.analysis-table td{{padding:8px 10px;border-bottom:1px solid #f0f0f0;color:#184341}}
.analysis-table tr:hover td{{background:#fafffe}}

.action-plan{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px;margin-bottom:20px}}
.action-group{{background:#F7F8FA;border-radius:10px;padding:16px}}
.action-group h4{{font-size:12px;font-weight:700;color:#00A19A;text-transform:uppercase;letter-spacing:.5px;margin-bottom:8px}}
.action-group ul{{font-size:12px;line-height:1.8;margin-left:16px;color:#333}}

.targeting-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px;margin-top:12px}}
.targeting-card{{background:#F7F8FA;border-radius:10px;padding:16px;border-left:3px solid var(--tc,#00A19A)}}
.targeting-card h4{{font-size:13px;font-weight:700;color:#184341;margin-bottom:8px}}
.targeting-card .tc-label{{font-size:10px;font-weight:700;color:#5a5a5a;text-transform:uppercase;letter-spacing:.5px;margin-top:8px;margin-bottom:2px}}
.targeting-card .tc-value{{font-size:13px;color:#184341}}
.targeting-card .tc-tags{{display:flex;flex-wrap:wrap;gap:4px;margin-top:4px}}
.targeting-card .tc-tag{{font-size:11px;background:#fff;border:1px solid #ddd;padding:2px 8px;border-radius:50px;color:#184341}}

/* ── KPI Grid ── */
.kpi-row{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:16px;margin-bottom:36px}}
.kpi{{background:#fff;padding:24px;border-radius:12px;box-shadow:0 2px 12px rgba(0,0,0,.04)}}
.kpi-l{{font-size:11px;color:#5a5a5a;text-transform:uppercase;letter-spacing:1px;font-weight:600;margin-bottom:6px}}
.kpi-v{{font-size:28px;font-weight:800;letter-spacing:-.02em;color:#184341}}
.kpi-v.cy{{color:#00A19A}}
.kpi-v.gr{{color:#22c55e}}

/* ── Section header ── */
.sh{{font-size:11px;font-weight:700;color:#5a5a5a;text-transform:uppercase;letter-spacing:1px;margin-bottom:16px;padding-bottom:8px;border-bottom:1px solid #eee}}

/* ── Funnel Visual ── */
.funnel-viz{{display:flex;flex-direction:column;align-items:center;margin-bottom:36px;padding:16px 0}}
.fv-step{{min-width:280px}}
.fv-inner{{display:flex;justify-content:space-between;align-items:center;padding:14px 20px;border-radius:10px;font-size:13px;font-weight:600}}
.fv-inner.ghost{{opacity:.3;border-style:dashed!important}}
.fv-inner.topo{{background:rgba(29,113,184,.08);border:1px solid rgba(29,113,184,.25);color:#1D71B8}}
.fv-inner.meio{{background:rgba(0,161,154,.08);border:1px solid rgba(0,161,154,.25);color:#00A19A}}
.fv-inner.fundo{{background:rgba(34,197,94,.08);border:1px solid rgba(34,197,94,.25);color:#16a34a}}
.fv-tag{{font-size:9px;letter-spacing:.12em;opacity:.6;min-width:44px}}
.fv-mid{{font-size:13px;flex:1;text-align:center}}
.fv-val{{font-weight:800;font-size:14px}}
.fv-arrow-line{{width:2px;height:18px;background:#eee;margin:0 auto}}

/* ── Chart ── */
.chart-wrap{{background:#fff;border-radius:12px;box-shadow:0 2px 12px rgba(0,0,0,.04);padding:24px;margin-bottom:36px}}

/* ── Stage sections ── */
.stage{{margin-bottom:28px;background:#fff;border-radius:12px;box-shadow:0 2px 12px rgba(0,0,0,.04);overflow:hidden;border-top:3px solid var(--sc)}}
.stage-inner{{padding:24px}}
.stage-top{{display:flex;align-items:center;gap:10px;margin-bottom:6px}}
.tag-pill{{padding:4px 12px;border-radius:50px;font-size:11px;font-weight:700;color:#fff;letter-spacing:.06em}}
.stage-name{{font-size:15px;font-weight:700;color:#184341}}
.stage-sub{{font-size:12px;color:#5a5a5a}}
.stage-desc{{font-size:12px;color:#5a5a5a;margin-bottom:16px;font-style:italic}}

.stage-kpis{{display:flex;gap:32px;margin-bottom:20px;flex-wrap:wrap}}
.sk{{display:flex;flex-direction:column}}
.sk-v{{font-size:20px;font-weight:800;color:#184341}}
.sk-l{{font-size:10px;color:#5a5a5a;margin-top:2px;text-transform:uppercase;letter-spacing:.5px;font-weight:600}}

.sub-header{{font-size:11px;font-weight:700;color:#184341;text-transform:uppercase;letter-spacing:1px;margin-bottom:10px}}

/* ── Campaign rows ── */
.camp-row{{display:flex;justify-content:space-between;align-items:center;padding:10px 14px;border-radius:8px;margin-bottom:4px;background:#F7F8FA;font-size:13px}}
.camp-row:hover{{background:#fafffe}}
.camp-left{{display:flex;align-items:center;gap:8px;flex:1;min-width:0}}
.dot{{width:8px;height:8px;border-radius:50%;flex-shrink:0}}
.dot.active{{background:#22c55e;animation:blink 2s infinite}}
.dot.paused{{background:#aaa}}
.camp-name-text{{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:#184341;font-weight:500}}
.budget-tag{{font-size:10px;color:#5a5a5a;flex-shrink:0}}
.camp-nums{{display:flex;gap:16px;font-size:12px;color:#5a5a5a;flex-shrink:0}}
.camp-nums span:first-child{{color:#184341;font-weight:700}}

/* ── Creative / Ad cards ── */
.creatives-section{{margin-top:20px}}
.ad-grid{{display:flex;flex-direction:column;gap:12px}}
.ad-card{{background:#F7F8FA;border:1px solid #eee;border-radius:12px;padding:16px;transition:all .15s}}
.ad-card:hover{{background:#fafffe;border-color:#00A19A;box-shadow:0 2px 8px rgba(0,161,154,.08)}}
.ad-top{{display:flex;gap:14px;margin-bottom:10px;align-items:flex-start}}
.ad-thumb{{width:80px;height:80px;border-radius:10px;object-fit:cover;flex-shrink:0;background:#eee}}
.ad-thumb-placeholder{{width:80px;height:80px;border-radius:10px;background:#eee;flex-shrink:0}}
.ad-info{{flex:1;min-width:0}}
.ad-name{{font-size:14px;font-weight:700;color:#184341;margin-bottom:3px}}
.ad-title{{font-size:12px;font-weight:600;color:var(--sc);margin-bottom:2px}}
.ad-desc{{font-size:11px;color:#5a5a5a}}
.ad-body{{font-size:12px;color:#5a5a5a;line-height:1.6;margin-bottom:12px;padding:12px;background:#fff;border-radius:8px;border-left:3px solid var(--sc)}}
.ad-metrics{{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin-bottom:8px}}
.am{{text-align:center}}
.am-v{{font-size:15px;font-weight:800;color:#184341;display:block}}
.am-v.highlight{{color:#22c55e}}
.am-l{{font-size:9px;color:#5a5a5a;text-transform:uppercase;letter-spacing:.5px;font-weight:600}}
.ad-bar{{height:6px;border-radius:3px;background:#eee}}
.ad-bar-fill{{height:100%;border-radius:3px;transition:width .3s}}

.empty{{padding:24px;text-align:center;color:#5a5a5a;font-size:14px}}
.empty-hint{{font-size:12px;color:#f59e0b;margin-top:6px;font-style:italic}}

/* ── Footer ── */
.footer{{max-width:1200px;margin:0 auto;text-align:center;padding:32px;font-size:11px;color:#5a5a5a;border-top:1px solid #eee}}
.footer-logo{{display:inline-flex;align-items:center;gap:6px;margin-bottom:4px}}
.footer-logo svg{{width:18px;height:18px}}
.footer-logo span{{font-size:14px;font-weight:800;background:linear-gradient(135deg,#38bdf8,#2dd4bf);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}

/* ── Mobile ── */
@media(max-width:768px){{
    .topbar{{padding:0 12px;height:52px;flex-wrap:nowrap}}
    .logo svg{{width:22px;height:22px}}
    .logo-text{{font-size:16px}}
    .topbar-right{{gap:6px}}
    .topbar-label{{display:none}}
    .topbar-badge{{font-size:9px;padding:4px 10px}}
    .period-select{{font-size:10px;padding:4px 24px 4px 8px}}

    .hero{{padding:20px 14px 16px}}
    .hero h1{{font-size:20px}}
    .hero-row{{flex-direction:column;align-items:stretch;gap:12px}}
    .hero-sub{{font-size:12px}}
    .bal{{text-align:left;min-width:auto;padding:12px 14px}}
    .bal-val{{font-size:24px}}

    .tabs{{padding:10px 14px 0;gap:4px}}
    .tab{{padding:8px 14px;font-size:11px;gap:5px}}
    .tab svg{{width:13px;height:13px}}

    .content{{padding:0 14px 40px}}
    .kpi-row{{grid-template-columns:repeat(2,1fr);gap:8px}}
    .kpi{{padding:14px 12px}}
    .kpi-v{{font-size:20px}}
    .kpi-l{{font-size:9px;letter-spacing:.5px}}

    .sh{{font-size:10px}}
    .funnel-viz{{padding:8px 0}}
    .fv-step{{min-width:auto}}
    .fv-inner{{font-size:10px;padding:10px 12px}}
    .fv-tag{{font-size:8px;min-width:36px}}
    .fv-val{{font-size:11px}}
    .fv-mid{{font-size:10px}}

    .chart-wrap{{padding:14px}}

    .stage{{margin-bottom:16px}}
    .stage-inner{{padding:14px}}
    .stage-top{{flex-wrap:wrap;gap:6px}}
    .stage-name{{font-size:13px}}
    .stage-sub{{font-size:10px}}
    .stage-desc{{font-size:11px;margin-bottom:10px}}
    .stage-kpis{{gap:12px;margin-bottom:14px}}
    .sk-v{{font-size:16px}}
    .sk-l{{font-size:9px}}

    .camp-row{{flex-direction:column;align-items:flex-start;gap:4px;padding:8px 10px}}
    .camp-nums{{display:flex;flex-wrap:wrap;gap:8px;font-size:10px}}
    .camp-name-text{{font-size:12px;white-space:normal}}

    .ad-card{{padding:12px}}
    .ad-top{{flex-direction:column;gap:8px}}
    .ad-thumb{{width:100%;height:160px;border-radius:8px}}
    .ad-thumb-placeholder{{width:100%;height:80px}}
    .ad-name{{font-size:13px}}
    .ad-body{{font-size:11px;padding:8px}}
    .ad-metrics{{grid-template-columns:repeat(3,1fr);gap:6px}}
    .am-v{{font-size:13px}}
    .am-l{{font-size:8px}}

    .report-card{{padding:20px 16px}}
    .report-card h2{{font-size:17px}}
    .report-card h3{{font-size:14px}}
    .report-card p{{font-size:13px}}
    .report-card ul{{font-size:12px;margin-left:14px}}
    .targeting-grid{{grid-template-columns:1fr}}
    .health-table{{font-size:11px}}
    .analysis-table{{font-size:11px}}
    .analysis-table th,.analysis-table td{{padding:6px 6px}}
    .action-plan{{grid-template-columns:1fr}}

    .footer{{padding:20px 14px;font-size:10px}}
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
        <select class="period-select" onchange="location.search='?period='+this.value">
            <option value="maximum" selected>Desde o início</option>
            <option value="last_7d">Últimos 7 dias</option>
            <option value="last_14d">Últimos 14 dias</option>
            <option value="last_30d">Últimos 30 dias</option>
        </select>
        <span class="topbar-badge">Inauguração</span>
    </div>
</div>

<div class="hero">
    <div class="hero-row">
        <div>
            <h1>Dashboard <span class="city">{unit['nome']}</span></h1>
            <p class="hero-sub">{p['account_name']} · {s['active']} de {s['total_camps']} campanhas ativas</p>
        </div>
        <div class="bal">
            <div class="bal-label">Saldo disponível</div>
            <div class="bal-val">R$ {b['remaining']:,.2f}</div>
            <div class="bal-det">Budget R$ {b['daily_budget']:,.0f}/dia{f" · ~{b['days_left']:.0f} dias" if 0<b['days_left']<999 else ""}</div>
            <div class="bal-bar"><div class="bal-bar-fill"></div></div>
        </div>
    </div>
</div>

<div class="tabs">
    <div class="tab active" onclick="switchTab('dashboard',this)">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>
        Dashboard
    </div>
    <div class="tab" onclick="switchTab('relatorio',this)">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><path d="M14 2v6h6"/><path d="M16 13H8"/><path d="M16 17H8"/><path d="M10 9H8"/></svg>
        Relatório
    </div>
    <div class="tab-divider"></div>
</div>

<div id="tab-dashboard" class="tab-content active">
<div class="content">
    <div class="kpi-row">
        <div class="kpi"><div class="kpi-l">Investido</div><div class="kpi-v cy">R$ {s['spend']:,.2f}</div></div>
        <div class="kpi"><div class="kpi-l">Alcance</div><div class="kpi-v">{s['reach']:,}</div></div>
        <div class="kpi"><div class="kpi-l">Cliques</div><div class="kpi-v">{s['clicks']:,}</div></div>
        <div class="kpi"><div class="kpi-l">CTR</div><div class="kpi-v">{s['ctr']:.2f}%</div></div>
        <div class="kpi"><div class="kpi-l">Conversas WPP</div><div class="kpi-v gr">{s['conversations']}</div></div>
        <div class="kpi"><div class="kpi-l">CPL</div><div class="kpi-v">{'R$ '+f"{s['cpl']:.2f}" if s['cpl']>0 else '—'}</div></div>
    </div>

    <div class="sh">Funil de Inauguração</div>
    {funnel_html}

    <div class="sh">Performance Diária</div>
    <div class="chart-wrap">
        <canvas id="chart" height="70"></canvas>
    </div>

    <div class="sh">Campanhas por Etapa do Funil</div>
    {stages_html}
</div>
</div><!-- /tab-dashboard -->

<div id="tab-relatorio" class="tab-content">
<div class="content">
    {_build_report_html(unit, p, now)}
</div>
</div><!-- /tab-relatorio -->

<div class="footer">
    <div class="footer-logo">
        <svg viewBox="0 0 24 24" fill="none" style="width:18px;height:18px;vertical-align:middle;filter:drop-shadow(0 0 4px rgba(56,189,248,.3))"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" fill="url(#lg3)"/><defs><linearGradient id="lg3" x1="3" y1="2" x2="21" y2="22"><stop stop-color="#38bdf8"/><stop offset="1" stop-color="#2dd4bf"/></linearGradient></defs></svg>
        <span>seven</span>
    </div>
    <div>marketing digital · atualizado em {now}</div>
</div>

<script>
new Chart(document.getElementById('chart'),{{
    type:'bar',
    data:{{
        labels:{chart_labels},
        datasets:[
            {{label:'Gasto (R$)',data:{chart_spend},backgroundColor:'rgba(0,161,154,.15)',borderColor:'#00A19A',borderWidth:1,borderRadius:6,yAxisID:'y',order:2}},
            {{label:'Conversas',data:{chart_convs},type:'line',borderColor:'#22c55e',backgroundColor:'rgba(34,197,94,.06)',pointBackgroundColor:'#22c55e',pointRadius:5,tension:.35,fill:true,yAxisID:'y1',order:1}},
            {{label:'Cliques',data:{chart_clicks},type:'line',borderColor:'#1D71B8',borderDash:[5,5],pointRadius:3,tension:.35,yAxisID:'y1',order:0}},
        ],
    }},
    options:{{
        responsive:true,
        interaction:{{mode:'index',intersect:false}},
        plugins:{{
            legend:{{labels:{{color:'#5a5a5a',font:{{family:'Montserrat',size:11,weight:'600'}},usePointStyle:true,pointStyle:'circle',padding:20}}}},
            tooltip:{{backgroundColor:'#184341',titleColor:'#fff',bodyColor:'rgba(255,255,255,.8)',borderColor:'rgba(255,255,255,.1)',borderWidth:1,cornerRadius:8,padding:12,titleFont:{{family:'Montserrat',weight:'700',size:12}},bodyFont:{{family:'Montserrat',size:11}}}},
        }},
        scales:{{
            x:{{ticks:{{color:'#5a5a5a',font:{{family:'Montserrat',size:11}}}},grid:{{display:false}}}},
            y:{{position:'left',title:{{display:true,text:'Gasto (R$)',color:'#00A19A',font:{{family:'Montserrat',size:11,weight:'600'}}}},ticks:{{color:'#5a5a5a',font:{{family:'Montserrat',size:10}}}},grid:{{color:'rgba(0,0,0,.04)'}}}},
            y1:{{position:'right',title:{{display:true,text:'Conversas / Cliques',color:'#22c55e',font:{{family:'Montserrat',size:11,weight:'600'}}}},ticks:{{color:'#5a5a5a',font:{{family:'Montserrat',size:10}}}},grid:{{display:false}}}},
        }},
    }},
}});
</script>
<script>
function switchTab(id, el) {{
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.getElementById('tab-'+id).classList.add('active');
    el.classList.add('active');
}}
</script>
</body>
</html>"""
    return html


def main():
    print("⚡ SEVEN — Dashboard Inauguração")
    print("=" * 40)

    for slug, unit in UNITS.items():
        print(f"\n📡 {unit['nome']} ({unit['estado']})...")
        raw = fetch_all(unit["account_id"])
        p = process(raw)

        s = p["summary"]
        b = p["balance"]
        print(f"  ✓ {s['total_camps']} campanhas ({s['active']} ativas)")
        print(f"  ✓ R$ {s['spend']:,.2f} investido · {s['conversations']} conversas WPP")
        print(f"  ✓ Saldo: R$ {b['remaining']:,.2f}")

        for sk in ["topo", "meio", "fundo"]:
            t = p["totals"][sk]
            ads_count = len(p["ad_data"][sk])
            print(f"  ✓ {sk.upper()}: R$ {t['spend']:,.2f} · {t['conversations']} conv · {ads_count} criativos")

        html = generate_html(slug, unit, p)
        out = Path("output") / f"dash_inauguracao_{slug}.html"
        out.parent.mkdir(exist_ok=True)
        out.write_text(html, encoding="utf-8")
        print(f"  ✅ {out}")

    print("\n🎉 Pronto!")


if __name__ == "__main__":
    main()
