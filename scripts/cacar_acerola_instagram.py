#!/usr/bin/env python3
"""
Caça ao packshot real — Hiper Frutas no Instagram (sessão do CRON).
Visita https://www.instagram.com/hiperfrutasoficial/ com o perfil Playwright
persistente (scripts/playwright_profile), fecha modais, rola o grid e extrai
URLs de imagens (cdninstagram) + legendas. Filtra posts com "acerola".
Não publica nada: só grava scratch/instagram_hiperfrutas.json.

Uso: functions/venv/bin/python3 scripts/cacar_acerola_instagram.py
"""
import json
import os
import sys
import time

from playwright.sync_api import sync_playwright

USER_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "playwright_profile"))
PERFIL = "https://www.instagram.com/hiperfrutasoficial/"
SAIDA = os.path.join(os.path.dirname(__file__), "..", "scratch", "instagram_hiperfrutas.json")


def main():
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            USER_DATA_DIR,
            headless=True,
            viewport={"width": 1280, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = ctx.new_page()
        page.goto(PERFIL, timeout=45000)
        time.sleep(4)

        # fecha modais comuns (cookies, "Salvar info", notificações)
        for seletor in ["text=Agora não", "text=Not Now", "text=Permitir", "button[aria-label='Fechar']",
                        "button[aria-label='Close']", "div[role='dialog'] button"]:
            try:
                btn = page.locator(seletor).first
                if btn.is_visible(timeout=1200):
                    btn.click()
                    time.sleep(1)
            except Exception:
                pass

        # rola o grid para carregar posts
        for _ in range(8):
            page.mouse.wheel(0, 1600)
            time.sleep(1.2)

        # extrai links dos posts do grid
        links = page.eval_on_selector_all(
            "a[href*='/p/'], a[href*='/reel/']",
            "els => els.map(e => e.href)",
        )
        links = list(dict.fromkeys(links))[:30]
        print(f"posts encontrados: {len(links)}")

        achados = []
        for i, link in enumerate(links):
            try:
                page.goto(link, timeout=30000)
                time.sleep(2)
                legenda = ""
                try:
                    legenda = page.eval_on_selector("h1", "e => e.textContent") or ""
                except Exception:
                    pass
                imgs = page.eval_on_selector_all(
                    "img[src*='cdninstagram']",
                    "els => els.map(e => e.src)",
                )
                img_principal = imgs[0] if imgs else ""
                if img_principal:
                    achados.append({"post": link, "legenda": legenda[:180], "img": img_principal})
                if "acerola" in (legenda or "").lower():
                    print(f"  🍒 ACEROLA: {link}  legenda={legenda[:80]}")
                time.sleep(1)
            except Exception as e:
                print(f"  skip {i}: {str(e)[:60]}")

        ctx.close()

    with open(SAIDA, "w") as f:
        json.dump(achados, f, ensure_ascii=False, indent=1)
    com_acerola = [a for a in achados if "acerola" in (a["legenda"] or "").lower()]
    print(f"\ntotal coletado: {len(achados)} | com 'acerola' na legenda: {len(com_acerola)}")
    if com_acerola:
        for a in com_acerola:
            print(f"  -> {a['img'][:100]}")


if __name__ == "__main__":
    main()
