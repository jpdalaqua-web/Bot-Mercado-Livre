# Bot de Afiliado — Mercado Livre

Duas formas de usar:
1. **Manual**: você cola o link de afiliado de um produto, o bot devolve o post pronto (imagem + título + preço de/por).
2. **Automático**: o bot busca sozinho, de tempos em tempos, produtos com desconto nas palavras-chave que você configurar, e te manda direto no Telegram.

⚠️ Importante sobre o modo automático: como o Mercado Livre não tem API pública para gerar link de afiliado, as ofertas encontradas automaticamente vêm com o **link normal do produto** (sem sua tag). Antes de postar, abra o link no app do ML e gere a versão de afiliado — leva uns 15 segundos por produto. É o único passo que continua manual.

## Passo 1 — Criar o bot no Telegram (2 minutos)

1. Abra o Telegram e procure por **@BotFather**.
2. Envie `/newbot`.
3. Escolha um nome (ex: `Meu Bot de Ofertas`).
4. Escolha um username terminando em `bot` (ex: `meusofertasbot`).
5. O BotFather vai te devolver um **token**, algo como:
   `123456789:AAExxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
   **Guarde esse token, é a chave do seu bot.**
6. Abra uma conversa com o seu bot (clique no link que o BotFather te deu) e mande `/start` — isso "ativa" o chat pra ele poder te responder depois.

## Passo 2 — Hospedar 24h no Railway (grátis pra começar)

1. Crie uma conta em https://railway.app (dá pra logar com GitHub).
2. Clique em **New Project → Deploy from GitHub repo**.
   - Se não tiver um repositório ainda: crie um repo novo no GitHub, suba estes 4 arquivos (`bot.py`, `requirements.txt`, `Procfile`, `README.md`) para lá, e então selecione esse repo no Railway.
3. Depois de importar o projeto, vá em **Variables** (aba do projeto) e adicione:
   - `TELEGRAM_BOT_TOKEN` = (cole o token que o BotFather te deu)
   - `WATCH_KEYWORDS` = palavras-chave separadas por vírgula, ex: `fone de ouvido,air fryer,mochila notebook` (deixe vazio se só quiser o modo manual)
   - `MIN_DISCOUNT` = desconto mínimo em % pra considerar oferta (padrão: `20`)
   - `CHECK_INTERVAL_MIN` = de quantos em quantos minutos buscar sozinho (padrão: `180` = 3h)
4. Vá em **Settings → Deploy** e confirme que o **Start Command** está usando o `Procfile` (`python bot.py`). O Railway detecta isso automaticamente na maioria dos casos.
5. Clique em **Deploy**. Em 1-2 minutos o bot fica no ar.
6. Teste: mande um link de produto do Mercado Livre pro seu bot no Telegram.

## Como usar no dia a dia

**Modo manual:**
1. Ache o produto no app do Mercado Livre.
2. Gere o link de afiliado pelo app/painel (Compartilhar → link de afiliado). ~30 segundos.
3. Cole esse link no chat com o seu bot.
4. O bot devolve a imagem + texto formatado com preço de/por.
5. Toque em copiar o texto e reenviar a foto no grupo do WhatsApp.

**Modo automático:**
1. Mande `/start` uma vez pro bot (isso registra seu chat pra ele saber pra onde te mandar as ofertas).
2. A cada `CHECK_INTERVAL_MIN` minutos, ele busca sozinho nas `WATCH_KEYWORDS` configuradas e te manda as que tiverem desconto ≥ `MIN_DISCOUNT`.
3. Quer forçar uma busca na hora? Manda `/ofertas` no chat.
4. Cada oferta encontrada automaticamente já vem com imagem, título e preço de/por — só falta você trocar o link pelo de afiliado (abrir no app → Compartilhar) antes de postar.
5. O bot guarda quais produtos já te enviou (`sent_items.json`) pra não repetir a mesma oferta.

## Rodando localmente (para testar antes de subir pro Railway)

```bash
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN="seu_token_aqui"
python bot.py
```

## Observações importantes

- O Mercado Livre **não tem API oficial para gerar o link de afiliado automaticamente** — por isso o passo de gerar o link ainda é manual (mas rápido). Ferramentas que prometem fazer isso 100% automático geralmente usam cookie de sessão da sua conta, o que viola os termos de uso e pode colocar sua conta de afiliado em risco.
- A API pública usada aqui (`api.mercadolibre.com/items/{id}`) só retorna `original_price` quando o produto está oficialmente em promoção no Mercado Livre — fora de promoção, o bot mostra só o preço atual.
- Fique de olho nas políticas de spam do WhatsApp (grupos) — evitar postar em excesso pro mesmo grupo pra não ser removido/bloqueado.
