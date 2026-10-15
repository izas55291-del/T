# ClipDrop — site web para publicar no Render

Este pacote contém uma versão web simples do ClipDrop (não é APK). O usuário abre o site, cola um link do TikTok, consulta formatos retornados pelo extrator e solicita o arquivo.

## Como publicar usando o navegador do celular
É necessário usar GitHub como ponte para o Render, pois este pacote não pode ser publicado no seu nome sem entrar na sua conta.

1. Baixe e extraia o ZIP no celular.
2. Crie uma conta em https://github.com/ e crie um repositório chamado `clipdrop`.
3. No repositório, use **Add file → Upload files** e envie `app.py`, `requirements.txt` e `render.yaml` que estão na raiz deste ZIP. Faça commit.
4. Entre em https://render.com/ e conecte sua conta GitHub.
5. Crie um **New Web Service** e selecione o repositório `clipdrop`.
6. Configure Build Command `pip install -r requirements.txt` e Start Command `gunicorn --bind 0.0.0.0:$PORT app:app`. Escolha o plano Free, se estiver disponível.
7. Aguarde a publicação e copie a URL HTTPS criada pelo Render. Abra a URL + `/health` para confirmar que o servidor responde.

## Limites
- Não foi publicado nem testado contra vídeos reais nesta sessão.
- A hospedagem gratuita pode dormir, limitar CPU, memória, tráfego ou encerrar downloads longos.
- O limite padrão é 100 MB, 900 segundos e uma operação simultânea.
- O site não solicita senhas, não acessa vídeos privados nem contorna autenticação ou restrições.
- As resoluções dependem dos metadados reais retornados pela fonte. A versão limpa só pode ser baixada quando a fonte oferece legitimamente um arquivo sem marca-d'água.
- Use somente vídeos que você tenha autorização para baixar. Antes de distribuir publicamente, crie uma política de privacidade e implemente controles adicionais contra abuso.
