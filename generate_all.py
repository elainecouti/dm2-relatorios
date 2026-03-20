#!/usr/bin/env python3
"""
Gera todos os dashboards: inauguração + clientes genéricos.
Cada cliente gera em sua própria subpasta (ex: cuiaba/index.html).
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

# ── Inauguração (template específico) ──
INAUG_UNITS = [
    {"slug": "cuiaba", "account_id": "934816888951624", "nome": "Cuiabá", "estado": "MT"},
    {"slug": "parauapebas-inaug", "account_id": "2428950724211358", "nome": "Parauapebas", "estado": "PA"},
]

# ── Clientes genéricos (template padrão) ──
CLIENTS = [
    # DM2 unidades ativas
    {"slug": "dm2-vitoria", "account_id": "224198366875813", "nome": "DM2 Vitória", "subtitle": "Doutor DM2 Diabetes"},
    {"slug": "dm2-valadares", "account_id": "1635940510764304", "nome": "DM2 Gov. Valadares", "subtitle": "Doutor DM2 Diabetes"},
    {"slug": "dm2-santo-amaro", "account_id": "348194284224016", "nome": "DM2 Santo Amaro", "subtitle": "Doutor DM2 Diabetes"},
    {"slug": "dm2-jundiai", "account_id": "1090387126061168", "nome": "DM2 Jundiaí", "subtitle": "Doutor DM2 Diabetes"},
    {"slug": "dm2-vila-velha", "account_id": "656207941120580", "nome": "DM2 Vila Velha", "subtitle": "Doutor DM2 Diabetes"},
    {"slug": "dm2-parauapebas", "account_id": "2428950724211358", "nome": "DM2 Parauapebas", "subtitle": "Doutor DM2 Diabetes"},
    {"slug": "dm2-recife", "account_id": "1178305167588983", "nome": "DM2 Recife", "subtitle": "Doutor DM2 Diabetes"},
    {"slug": "dm2-colatina", "account_id": "1072431374112785", "nome": "DM2 Colatina", "subtitle": "Doutor DM2 Diabetes"},
    {"slug": "dm2-eunapolis", "account_id": "1784445365367247", "nome": "DM2 Eunápolis", "subtitle": "Doutor DM2 Diabetes"},
    {"slug": "dm2-rio-preto", "account_id": "7051741331607785", "nome": "DM2 Rio Preto", "subtitle": "Doutor DM2 Diabetes"},
    {"slug": "dm2-montes-claros", "account_id": "369112886083429", "nome": "DM2 Montes Claros", "subtitle": "Doutor DM2 Diabetes"},
    {"slug": "dm2-lapa", "account_id": "1814738238937234", "nome": "DM2 Lapa", "subtitle": "Doutor DM2 Diabetes"},
    {"slug": "dm2-cachoeiro", "account_id": "423311083553168", "nome": "DM2 Cachoeiro", "subtitle": "Doutor DM2 Diabetes"},
    {"slug": "dm2-marilia", "account_id": "1375785539722457", "nome": "DM2 Marília", "subtitle": "Doutor DM2 Diabetes"},
    {"slug": "dm2-linhares", "account_id": "1259599491668065", "nome": "DM2 Linhares", "subtitle": "Doutor DM2 Diabetes"},
    {"slug": "dm2-campos", "account_id": "1251606756193644", "nome": "DM2 Campos", "subtitle": "Doutor DM2 Diabetes"},
    {"slug": "dm2-anapolis", "account_id": "610262074698354", "nome": "DM2 Anápolis", "subtitle": "Doutor DM2 Diabetes"},
    {"slug": "dm2-maringa", "account_id": "749354830984301", "nome": "DM2 Maringá", "subtitle": "Doutor DM2 Diabetes"},
    {"slug": "dm2-osasco", "account_id": "1271496400805585", "nome": "DM2 Osasco", "subtitle": "Doutor DM2 Diabetes"},
    {"slug": "dm2-sao-luis", "account_id": "2018106368930952", "nome": "DM2 São Luís", "subtitle": "Doutor DM2 Diabetes"},
    {"slug": "dm2-caxias", "account_id": "3982423972018834", "nome": "DM2 Caxias", "subtitle": "Doutor DM2 Diabetes"},
    {"slug": "dm2-campo-grande", "account_id": "1127834142769964", "nome": "DM2 Campo Grande", "subtitle": "Doutor DM2 Diabetes"},
    {"slug": "dm2-brasilia", "account_id": "1926250058223238", "nome": "DM2 Brasília", "subtitle": "Doutor DM2 Diabetes"},
    {"slug": "dm2-imperatriz", "account_id": "1438295780977933", "nome": "DM2 Imperatriz", "subtitle": "Doutor DM2 Diabetes"},
    # Emagrecentro
    {"slug": "emagrecentro-cariacica", "account_id": "1165997078803892", "nome": "Emagrecentro Cariacica", "subtitle": "Emagrecentro"},
    {"slug": "emagrecentro-vv", "account_id": "1067896645109140", "nome": "Emagrecentro Vila Velha", "subtitle": "Emagrecentro"},
    {"slug": "emagrecentro-vix", "account_id": "1123165082806200", "nome": "Emagrecentro Vitória", "subtitle": "Emagrecentro"},
    # CDT
    {"slug": "cdt-vitoria", "account_id": "440545560762864", "nome": "CDT Vitória", "subtitle": "Cartão de Todos"},
    # Max Outlet
    {"slug": "max-outlet", "account_id": "1242614463111951", "nome": "Max Outlet", "subtitle": "E-commerce"},
    # Médicos
    {"slug": "dra-leandro", "account_id": "940902802342405", "nome": "Dr. Leandro Maia", "subtitle": "Tráfego Médico"},
    {"slug": "dra-alessandra", "account_id": "820404770803811", "nome": "Dra. Alessandra", "subtitle": "Tráfego Médico"},
    {"slug": "dra-chris", "account_id": "1182463057290047", "nome": "Dra. Chris Barros", "subtitle": "Tráfego Médico"},
    # Cibelly
    {"slug": "cibelly", "account_id": "893001683526806", "nome": "Cibelly Cordeiro", "subtitle": "Expert / Eventos"},
]


def main():
    # ── Gerar dashboards de inauguração ──
    from dash_inauguracao import fetch_all as inaug_fetch, process as inaug_process, generate_html as inaug_html

    for u in INAUG_UNITS:
        slug = u["slug"]
        print(f"\n⚡ [INAUG] {u['nome']} ({u['estado']})...")
        try:
            raw = inaug_fetch(u["account_id"])
            p = inaug_process(raw)
            s = p["summary"]
            print(f"  ✓ {s['total_camps']} campanhas · R$ {s['spend']:,.2f} · {s['conversations']} conversas")
            html = inaug_html(slug, {"nome": u["nome"], "estado": u["estado"], "account_id": u["account_id"]}, p)
            out_dir = Path(slug)
            out_dir.mkdir(exist_ok=True)
            (out_dir / "index.html").write_text(html, encoding="utf-8")
            print(f"  ✅ {slug}/index.html")
        except Exception as e:
            print(f"  ❌ Erro: {e}")

    # ── Gerar dashboards genéricos ──
    from dash_generico import fetch_all as gen_fetch, process as gen_process, generate_html as gen_html

    for c in CLIENTS:
        slug = c["slug"]
        print(f"\n⚡ [GENÉRICO] {c['nome']}...")
        try:
            raw = gen_fetch(c["account_id"])
            p = gen_process(raw)
            s = p["summary"]
            print(f"  ✓ {s['total_camps']} campanhas · R$ {s['spend']:,.2f} · {s['clicks']} cliques")
            html = gen_html(slug, {"nome": c["nome"], "subtitle": c.get("subtitle", "")}, p)
            out_dir = Path(slug)
            out_dir.mkdir(exist_ok=True)
            (out_dir / "index.html").write_text(html, encoding="utf-8")
            print(f"  ✅ {slug}/index.html")
        except Exception as e:
            print(f"  ❌ Erro: {e}")

    print("\n🎉 Todos os dashboards gerados!")


if __name__ == "__main__":
    main()
