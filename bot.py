
"""
Bot de Afiliado - Mercado Livre
--------------------------------
Fluxo:
1. Você gera o link de afiliado no app/painel do Mercado Livre (~30s).
2. Cola esse link aqui no bot (no seu chat privado com ele).
3. O bot busca automaticamente: título, imagem, preço "de/por" e desconto.
4. Ele te devolve o post pronto (imagem + texto) para você copiar/reenviar no WhatsApp.
"""

import os
import re
import json
import logging
import requests
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

# --- Configuração da busca automática de ofertas ---
# Palavras-chave a monitorar, separadas por vírgula. Ex: "fone de ouvido,air fryer,mochila"
WATCH_KEYWORDS = [k.strip() for k in os.environ.get("WATCH_KEYWORDS", "").split(",") if k.strip()]
# Desconto mínimo (%) para considerar "oferta"
MIN_DISCOUNT = int(os.environ.get("MIN_DISCOUNT", "20"))
# De quanto em quanto tempo checar (minutos)
CHECK_INTERVAL_MIN = int(os.environ.get("CHECK_INTERVAL_MIN", "180"))
# Quantos resultados olhar por palavra-chave a cada checagem
RESULTS_PER_KEYWORD = int(os.environ.get("RESULTS_PER_KEYWORD", "20"))

SUBSCRIBER_FILE = "subscriber.json"
SENT_ITEMS_FILE = "sent_items.json"

# Extrai o ID do produto (formato MLB1234567890, sempre 9-10 dígitos) de qualquer link do Mercado Livre
# (?<!\d) e (?!\d) evitam pegar números concatenados por engano (ex: MLB123456789 grudado em outro número)
ITEM_ID_REGEX = re.compile(r"(?<!\d)(MLB-?\d{9,10})(?!\d)", re.IGNORECASE)


def resolver_link_curto(url: str) -> tuple[str, str]:
    """Segue o redirecionamento de links curtos (meli.la, /sec/) e retorna (url_final, html_da_pagina)."""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        resp = requests.get(url, allow_redirects=True, timeout=10, headers=headers)
        return resp.url, resp.text
    except Exception as e:
        logger.warning(f"Não consegui resolver link curto {url}: {e}")
        return url, ""


# Tenta achar a URL "oficial" da página (mais confiável que vasculhar o HTML inteiro)
CANONICAL_REGEX = re.compile(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', re.IGNORECASE)
OG_URL_REGEX = re.compile(r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\']([^"\']+)["\']', re.IGNORECASE)


def extrair_url_oficial(html: str) -> str | None:
    for regex in (CANONICAL_REGEX, OG_URL_REGEX):
        match = regex.search(html)
        if match:
            return match.group(1)
    return None


# Prioridade: o parâmetro item_id na URL é o anúncio real (o /p/MLB... do path é só o produto de catálogo)
ITEM_ID_PARAM_REGEX = re.compile(r"item_id[=%3A]+(MLB-?\d{9,10})", re.IGNORECASE)


def extrair_item_id(url: str) -> str | None:
    # Prioriza o item_id do parâmetro (anúncio real) sobre o ID de catálogo (/p/MLB...) que aparece no path
    match_param = ITEM_ID_PARAM_REGEX.search(url)
    if match_param:
        return match_param.group(1).replace("-", "").upper()

    match = ITEM_ID_REGEX.search(url)
    if not match:
        return None
    return match.group(1).replace("-", "").upper()


def buscar_produto(item_id: str) -> dict | None:
    """Consulta a API pública do Mercado Livre para pegar dados do produto."""
    try:
        resp = requests.get(f"https://api.mercadolibre.com/items/{item_id}", timeout=10)
        resp.raise_for_status()
        data = resp.json()

        preco_atual = data.get("price")
        preco_original = data.get("original_price")  # só vem preenchido se estiver em promoção
        titulo = data.get("title", "Produto")
        imagem = data.get("thumbnail", "").replace("http://", "https://")
        # imagem em melhor qualidade
        imagem = imagem.replace("-I.jpg", "-O.jpg") if imagem else None

        return {
            "titulo": titulo,
            "imagem": imagem,
            "preco_atual": preco_atual,
            "preco_original": preco_original,
        }
    except Exception as e:
        logger.error(f"Erro ao buscar produto {item_id}: {e}")
        return None


def carregar_json(caminho: str, padrao):
    if os.path.exists(caminho):
        try:
            with open(caminho, "r") as f:
                return json.load(f)
        except Exception:
            return padrao
    return padrao


def salvar_json(caminho: str, dado):
    with open(caminho, "w") as f:
        json.dump(dado, f)


def salvar_chat_id(chat_id: int):
    salvar_json(SUBSCRIBER_FILE, {"chat_id": chat_id})


def carregar_chat_id() -> int | None:
    dado = carregar_json(SUBSCRIBER_FILE, {})
    return dado.get("chat_id")


def buscar_ofertas(keyword: str, limit: int = 20) -> list[dict]:
    """Busca produtos por palavra-chave na API pública e filtra os que estão com desconto."""
    try:
        resp = requests.get(
            "https://api.mercadolibre.com/sites/MLB/search",
            params={"q": keyword, "limit": limit},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error(f"Erro ao buscar ofertas para '{keyword}': {e}")
        return []

    ofertas = []
    for item in data.get("results", []):
        preco = item.get("price")
        preco_original = item.get("original_price")
        if not preco or not preco_original or preco_original <= preco:
            continue
        desconto = round((1 - preco / preco_original) * 100)
        if desconto < MIN_DISCOUNT:
            continue
        ofertas.append({
            "id": item.get("id"),
            "titulo": item.get("title"),
            "imagem": (item.get("thumbnail") or "").replace("http://", "https://").replace("-I.jpg", "-O.jpg"),
            "preco_atual": preco,
            "preco_original": preco_original,
            "desconto": desconto,
            "link": item.get("permalink"),
        })
    return ofertas


def formatar_preco(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def montar_texto(produto: dict, link_afiliado: str) -> str:
    titulo = produto["titulo"]
    atual = produto["preco_atual"]
    original = produto["preco_original"]

    linhas = [f"🔥 *{titulo}*", ""]

    if original and original > atual:
        desconto = round((1 - atual / original) * 100)
        linhas.append(f"~De {formatar_preco(original)}~")
        linhas.append(f"👉 Por *{formatar_preco(atual)}* ({desconto}% OFF)")
    else:
        linhas.append(f"👉 Por *{formatar_preco(atual)}*")

    linhas.append("")
    linhas.append(f"🛒 {link_afiliado}")

    return "\n".join(linhas)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    salvar_chat_id(update.effective_chat.id)
    palavras = ", ".join(WATCH_KEYWORDS) if WATCH_KEYWORDS else "(nenhuma configurada ainda)"
    await update.message.reply_text(
        "Bot ativado! ✅\n\n"
        "1️⃣ Cole aqui o link de um produto (com sua tag de afiliado) que eu monto o post pronto.\n"
        f"2️⃣ Também vou buscar ofertas sozinho a cada {CHECK_INTERVAL_MIN // 60}h nas palavras-chave: {palavras}\n"
        "   (mude isso na variável WATCH_KEYWORDS no servidor)\n"
        "3️⃣ Ou digite /ofertas a qualquer momento pra eu buscar agora.\n\n"
        "⚠️ Nas ofertas que eu encontrar sozinho, o link ainda vem sem sua tag de afiliado "
        "— é só abrir o link no app do ML e gerar a versão de afiliado antes de postar."
    )


async def enviar_ofertas(chat_id: int, context: ContextTypes.DEFAULT_TYPE, manual: bool = False):
    if not WATCH_KEYWORDS:
        if manual:
            await context.bot.send_message(chat_id, "Nenhuma palavra-chave configurada. Defina WATCH_KEYWORDS no servidor.")
        return

    ja_enviados = set(carregar_json(SENT_ITEMS_FILE, []))
    novos_enviados = []
    encontrou_algo = False

    for palavra in WATCH_KEYWORDS:
        for oferta in buscar_ofertas(palavra, RESULTS_PER_KEYWORD):
            if oferta["id"] in ja_enviados:
                continue
            encontrou_algo = True
            novos_enviados.append(oferta["id"])

            produto = {
                "titulo": oferta["titulo"],
                "preco_atual": oferta["preco_atual"],
                "preco_original": oferta["preco_original"],
            }
            texto = montar_texto(produto, oferta["link"]) + "\n\n⚠️ Link sem tag de afiliado ainda — gere a sua antes de postar."

            try:
                if oferta["imagem"]:
                    await context.bot.send_photo(chat_id, photo=oferta["imagem"], caption=texto, parse_mode="Markdown")
                else:
                    await context.bot.send_message(chat_id, texto, parse_mode="Markdown")
            except Exception as e:
                logger.warning(f"Falha ao enviar oferta {oferta['id']}: {e}")

    if novos_enviados:
        salvar_json(SENT_ITEMS_FILE, list(ja_enviados | set(novos_enviados)))

    if manual and not encontrou_algo:
        await context.bot.send_message(chat_id, "Nenhuma oferta nova encontrada agora. Tento de novo mais tarde 👍")


async def comando_ofertas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    salvar_chat_id(update.effective_chat.id)
    await update.message.reply_text("🔎 Buscando ofertas agora...")
    await enviar_ofertas(update.effective_chat.id, context, manual=True)


async def checagem_periodica(context: ContextTypes.DEFAULT_TYPE):
    chat_id = carregar_chat_id()
    if chat_id:
        await enviar_ofertas(chat_id, context, manual=False)


async def processar_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()

    if "mercadolivre" not in texto and "mercadolibre" not in texto and "meli" not in texto.lower():
        await update.message.reply_text("Manda um link do Mercado Livre 🙂")
        return

    item_id = extrair_item_id(texto)

    if not item_id:
        # Pode ser um link curto (meli.la, /sec/) — segue o redirecionamento
        url_final, html_pagina = resolver_link_curto(texto)
        item_id = extrair_item_id(url_final)

        if not item_id and html_pagina:
            # Prioriza a URL "oficial" da página (mais confiável que vasculhar o HTML inteiro)
            url_oficial = extrair_url_oficial(html_pagina)
            if url_oficial:
                item_id = extrair_item_id(url_oficial)

        if not item_id and html_pagina:
            # Último recurso: procura qualquer código MLB no HTML inteiro
            item_id = extrair_item_id(html_pagina)

    if not item_id:
        await update.message.reply_text(
            "Não consegui identificar o produto nesse link. "
            "Tenta usar o link direto do produto (não o encurtado /sec/)."
        )
        return

    await update.message.reply_text("🔎 Buscando dados do produto...")

    produto = buscar_produto(item_id)
    if not produto or produto["preco_atual"] is None:
        await update.message.reply_text(f"Não consegui puxar os dados desse produto (ID identificado: {item_id}). Confere o link e tenta de novo.")
        return

    post = montar_texto(produto, texto)

    if produto["imagem"]:
        try:
            await update.message.reply_photo(photo=produto["imagem"], caption=post, parse_mode="Markdown")
            return
        except Exception as e:
            logger.warning(f"Falha ao enviar foto, enviando só texto: {e}")

    await update.message.reply_text(post, parse_mode="Markdown")


def main():
    if not BOT_TOKEN:
        raise RuntimeError("Defina a variável de ambiente TELEGRAM_BOT_TOKEN")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ofertas", comando_ofertas))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, processar_link))

    if WATCH_KEYWORDS:
        app.job_queue.run_repeating(checagem_periodica, interval=CHECK_INTERVAL_MIN * 60, first=30)

    logger.info("Bot rodando...")
    app.run_polling()


if __name__ == "__main__":
    main()
