import os, re, socket, ipaddress, tempfile, threading
from urllib.parse import urlparse
from flask import Flask, request, render_template_string, send_file
import yt_dlp

app = Flask(__name__)
MAX_MB = int(os.getenv("MAX_DOWNLOAD_MB", "100"))
MAX_DURATION = int(os.getenv("MAX_DURATION_SECONDS", "900"))
LOCK = threading.BoundedSemaphore(int(os.getenv("MAX_CONCURRENT", "1")))
ALLOWED = {"tiktok.com","www.tiktok.com","m.tiktok.com","vm.tiktok.com","vt.tiktok.com","t.tiktok.com"}
PAGE = r"""
<!doctype html><html lang="pt-br"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ClipDrop</title><style>
*{box-sizing:border-box}body{margin:0;background:#09101c;color:#edf6ff;font:16px system-ui,sans-serif;padding:24px 16px}
main{max-width:620px;margin:auto}.logo{font-size:30px;font-weight:850;letter-spacing:-1px}.logo span{color:#48dfc0}
p{color:#a9b9cc;line-height:1.5}.card{background:#121e30;border:1px solid #26364c;border-radius:18px;padding:18px;margin-top:18px}
label{display:block;margin:8px 0;color:#c8d6e6}input,select,button{font:inherit;width:100%;padding:14px;border-radius:12px;margin:6px 0 12px}
input,select{background:#0b1423;color:white;border:1px solid #33465e}button{border:0;background:linear-gradient(100deg,#42dfbf,#4aa8ff);color:#07131f;font-weight:800;cursor:pointer}
.muted{font-size:13px;color:#91a4ba}.error{color:#ffaaa8}.success{color:#6ce6c5}.quality{padding:12px;background:#0b1423;border-radius:10px;margin:8px 0}
</style></head><body><main><div class="logo">Clip<span>Drop</span></div>
<p>Consulte formatos disponíveis e baixe vídeos públicos que você tem autorização para utilizar.</p>
<div class="card"><form method="post" action="/info"><label for="url">Link do TikTok</label>
<input id="url" name="url" value="{{ url|e }}" placeholder="https://www.tiktok.com/@usuario/video/..." required>
<button type="submit">Buscar vídeo</button></form>
{% if error %}<p class="error">{{error}}</p>{% endif %}
{% if video %}<hr style="border-color:#26364c"><h3>{{video.title}}</h3><p>Criador: {{video.creator}}</p>
<form method="post" action="/download"><input type="hidden" name="url" value="{{url|e}}">
<label for="format_id">Qualidade informada pela fonte</label><select id="format_id" name="format_id">
{% for f in video.formats %}<option value="{{f.id}}">{{f.label}}</option>{% endfor %}</select><button type="submit">Baixar vídeo</button></form>
{% endif %}</div>
<div class="card muted">Não solicita senha nem acessa vídeos privados. A qualidade depende dos formatos realmente acessíveis; versão sem marca-d'água só quando a fonte oferece um arquivo limpo legitimamente. O plano gratuito pode limitar downloads e suspender o site por inatividade. Use apenas conteúdo autorizado.</div>
</main></body></html>
"""
class Problem(Exception): pass

def validate(raw):
    if not isinstance(raw,str) or len(raw)>2048: raise Problem("Cole um link válido.")
    u=urlparse(raw.strip()); host=(u.hostname or "").lower().rstrip(".")
    if u.scheme!="https" or not host or u.username or u.password: raise Problem("Use uma URL HTTPS válida.")
    if not (host in ALLOWED or host.endswith(".tiktok.com")): raise Problem("Por segurança, aceito somente links do TikTok.")
    try:
        for x in socket.getaddrinfo(host,443,type=socket.SOCK_STREAM):
            if not ipaddress.ip_address(x[4][0]).is_global: raise Problem("O domínio resolveu para um endereço não público.")
    except socket.gaierror: raise Problem("Não consegui localizar o domínio do link.")
    return raw.strip()

def get_info(url):
    try:
        with yt_dlp.YoutubeDL({"quiet":True,"no_warnings":True,"noplaylist":True,"socket_timeout":15,"retries":1,"cachedir":False,"skip_download":True}) as y:
            info=y.extract_info(url,download=False)
    except Exception: raise Problem("Não consegui acessar o vídeo. Ele pode estar privado, removido, bloqueado ou indisponível.")
    if not info or info.get("_type")=="playlist": raise Problem("O link não corresponde a um vídeo individual acessível.")
    if info.get("duration") and info["duration"]>MAX_DURATION: raise Problem(f"Vídeo acima do limite de {MAX_DURATION} segundos.")
    formats=[]; seen=set()
    for f in sorted(info.get("formats") or [],key=lambda z:(z.get("height") or 0,z.get("acodec") not in (None,"none")),reverse=True):
        fid=str(f.get("format_id") or "")
        if not f.get("url") or f.get("vcodec") in (None,"none") or not fid or fid in seen: continue
        seen.add(fid); h=f.get("height"); label=f"{h}p" if h else "Resolução não informada"
        if f.get("ext"): label+=" · "+f["ext"]
        if f.get("acodec") in (None,"none"): label+=" · vídeo sem áudio separado"
        size=f.get("filesize") or f.get("filesize_approx")
        if size: label+=f" · {size/1048576:.1f} MB"
        formats.append({"id":fid,"label":label})
    if not formats: raise Problem("A fonte não informou formatos de vídeo compatíveis.")
    return {"title":info.get("title") or "Vídeo do TikTok","creator":info.get("uploader") or info.get("creator") or info.get("channel") or "Não informado","formats":formats}

@app.get("/")
def home(): return render_template_string(PAGE,url="",video=None,error=None)

@app.post("/info")
def info():
    url=request.form.get("url","")
    try:
        url=validate(url)
        if not LOCK.acquire(blocking=False): raise Problem("Servidor ocupado. Tente novamente em instantes.")
        try: video=get_info(url)
        finally: LOCK.release()
        return render_template_string(PAGE,url=url,video=video,error=None)
    except Problem as e: return render_template_string(PAGE,url=url,video=None,error=str(e)),400

@app.post("/download")
def download():
    url=request.form.get("url",""); fid=request.form.get("format_id","")
    temp=tempfile.TemporaryDirectory(prefix="clipdrop-")
    if not LOCK.acquire(blocking=False):
        temp.cleanup(); return render_template_string(PAGE,url=url,video=None,error="Servidor ocupado. Tente novamente."),429
    try:
        url=validate(url); info=get_info(url)
        if fid not in {f["id"] for f in info["formats"]}: raise Problem("Formato indisponível. Busque o vídeo novamente.")
        opts={"quiet":True,"no_warnings":True,"noplaylist":True,"outtmpl":os.path.join(temp.name,"clipdrop.%(ext)s"),"format":fid,"max_filesize":MAX_MB*1024*1024,"socket_timeout":20,"retries":1,"cachedir":False}
        with yt_dlp.YoutubeDL(opts) as y: y.download([url])
        found=[os.path.join(temp.name,n) for n in os.listdir(temp.name) if os.path.isfile(os.path.join(temp.name,n))]
        if not found: raise Problem("A fonte não entregou um arquivo de vídeo.")
        path=found[0]
        if os.path.getsize(path)>MAX_MB*1024*1024: raise Problem(f"Arquivo acima do limite de {MAX_MB} MB.")
        # Send the file and clean temporary storage when response is closed.
        resp=send_file(path,as_attachment=True,download_name="clipdrop-video."+path.rsplit(".",1)[-1])
        resp.call_on_close(temp.cleanup); resp.call_on_close(LOCK.release)
        return resp
    except Problem as e:
        temp.cleanup(); LOCK.release()
        return render_template_string(PAGE,url=url,video=None,error=str(e)),400
    except Exception:
        temp.cleanup(); LOCK.release()
        return render_template_string(PAGE,url=url,video=None,error="Falha no download. Tente novamente mais tarde ou com outro formato."),502

@app.get("/health")
def health(): return {"ok":True,"service":"ClipDrop"}

if __name__=="__main__": app.run(host="0.0.0.0",port=int(os.getenv("PORT","8080")))
