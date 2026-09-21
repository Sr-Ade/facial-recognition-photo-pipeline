"""Gera um relatório HTML visual (miniatura da foto + pessoas reconhecidas)
a partir de um CSV de reconhecimento, para conferência humana rápida sem
abrir link por link.

Uso:
    python -m src.generate_html_report data/recognition_result.csv
"""

import sys
import csv
import re
from collections import defaultdict


def extrair_file_id(link: str) -> str | None:
    m = re.search(r"/d/([^/]+)/", link)
    return m.group(1) if m else None


def main():
    if len(sys.argv) < 2:
        print("Uso: python -m src.generate_html_report <arquivo.csv>")
        return

    caminho = sys.argv[1]
    saida = caminho.replace(".csv", "") + "_report.html"

    with open(caminho, encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))

    por_foto = defaultdict(list)
    for row in linhas:
        por_foto[row["foto"]].append(row)

    cards = []
    for foto, rows in por_foto.items():
        link = rows[0]["link_foto"]
        file_id = extrair_file_id(link)
        thumb = f"https://drive.google.com/thumbnail?id={file_id}&sz=w500" if file_id else ""

        resultados_html = ""
        for row in rows:
            pessoa_id, confianca = row.get("pessoa_id", ""), row.get("confianca", "")
            if pessoa_id:
                try:
                    cor = "#2e7d32" if float(confianca) >= 97 else "#f9a825"
                except ValueError:
                    cor = "#f9a825"
                resultados_html += f'<div style="color:{cor};font-weight:600;">{pessoa_id} — {confianca}%</div>'
            else:
                resultados_html += f'<div style="color:#999;">— {confianca or "sem reconhecimento"}</div>'

        cards.append(f"""
        <div style="border:1px solid #ddd;border-radius:8px;padding:12px;width:280px;">
            <a href="{link}" target="_blank">
                <img src="{thumb}" style="width:100%;border-radius:6px;object-fit:cover;height:200px;background:#eee;" />
            </a>
            <div style="margin-top:8px;font-size:13px;font-weight:600;">{foto}</div>
            <div style="margin-top:4px;font-size:13px;">{resultados_html}</div>
        </div>
        """)

    html = f"""
    <html><head><meta charset="utf-8"><title>Recognition report</title></head>
    <body style="font-family:Arial, sans-serif;background:#fafafa;padding:24px;">
        <h2>{caminho}</h2>
        <p>{len(por_foto)} fotos</p>
        <div style="display:flex;flex-wrap:wrap;gap:16px;">{''.join(cards)}</div>
    </body></html>
    """

    with open(saida, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Relatório gerado: {saida}")


if __name__ == "__main__":
    main()
