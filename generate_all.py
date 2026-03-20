#!/usr/bin/env python3
"""
Gera dashboards de inauguração para todas as unidades.
Cada unidade gera em sua própria subpasta (ex: cuiaba/index.html).
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from dash_inauguracao import fetch_all, process, generate_html

UNITS = [
    {"slug": "cuiaba", "account_id": "934816888951624", "nome": "Cuiabá", "estado": "MT"},
    {"slug": "parauapebas-inaug", "account_id": "2428950724211358", "nome": "Parauapebas", "estado": "PA"},
]


def main():
    for u in UNITS:
        slug = u["slug"]
        print(f"\n⚡ Gerando dashboard: {u['nome']} ({u['estado']})...")

        raw = fetch_all(u["account_id"])
        p = process(raw)

        s = p["summary"]
        b = p["balance"]
        print(f"  ✓ {s['total_camps']} campanhas ({s['active']} ativas)")
        print(f"  ✓ R$ {s['spend']:,.2f} investido · {s['conversations']} conversas WPP")
        print(f"  ✓ Saldo: R$ {b['remaining']:,.2f} · Budget R$ {b['daily_budget']:,.0f}/dia")

        html = generate_html(slug, {"nome": u["nome"], "estado": u["estado"], "account_id": u["account_id"]}, p)

        out_dir = Path(slug)
        out_dir.mkdir(exist_ok=True)
        (out_dir / "index.html").write_text(html, encoding="utf-8")
        print(f"  ✅ {slug}/index.html gerado!")

    print("\n🎉 Todos os dashboards gerados!")


if __name__ == "__main__":
    main()
