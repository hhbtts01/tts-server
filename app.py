# -*- coding: utf-8 -*-
"""
自己的 TTS 服务（基于 edge-tts，白嫖微软语音接口）
- GET  /            网页版试用界面
- GET  /api/voices  获取可用音色列表
- GET  /api/tts?text=你好&voice=zh-CN-XiaoxiaoNeural  返回 mp3 音频
- POST /api/tts     JSON 方式调用 {"text": "...", "voice": "..."}
"""
import io
import os
from pathlib import Path

import edge_tts
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response

app = FastAPI(title="我的TTS服务", version="1.0")

# 允许跨域，方便别的网页/小程序调用
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DEFAULT_VOICE = os.environ.get("TTS_VOICE", "zh-CN-XiaoxiaoNeural")

# 常用中文音色（完整列表见 /api/voices）
POPULAR_VOICES = [
    "zh-CN-XiaoxiaoNeural",      # 女声 晓晓（最常用）
    "zh-CN-XiaoyiNeural",        # 女声 晓伊
    "zh-CN-YunxiNeural",         # 男声 云希
    "zh-CN-YunjianNeural",       # 男声 云健
    "zh-CN-YunyangNeural",       # 男声 云扬（新闻播音腔）
    "zh-CN-liaoning-XiaobeiNeural",  # 东北话 女声
    "zh-CN-shaanxi-XiaoniNeural",    # 陕西方言 女声
    "zh-HK-HiuMaanNeural",       # 粤语 女声
    "zh-HK-WanLungNeural",       # 粤语 男声
]

PAGE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>我的TTS</title>
<style>
  body{font-family:system-ui,-apple-system,"Microsoft YaHei",sans-serif;max-width:640px;margin:32px auto;padding:0 16px;color:#222}
  h1{font-size:22px}
  textarea{width:100%;height:110px;padding:10px;font-size:16px;box-sizing:border-box}
  select,button{font-size:16px;padding:8px 12px;margin-top:10px}
  button{background:#2563eb;color:#fff;border:0;border-radius:6px;cursor:pointer}
  button:disabled{background:#9db4e8}
  audio{width:100%;margin-top:14px}
  #tip{color:#888;font-size:13px;margin-top:8px;min-height:18px}
</style>
</head>
<body>
<h1>🔊 我的TTS（微软音色）</h1>
<textarea id="text" placeholder="输入要转成语音的文字...">大家好，我是乎乎猪，这是我自己搭的语音合成服务。</textarea><br>
<select id="voice"></select><br>
<button id="go" onclick="make()">生成语音</button>
<div id="tip"></div>
<audio id="player" controls></audio>
<script>
fetch('/api/voices').then(r=>r.json()).then(v=>{
  const sel=document.getElementById('voice');
  v.forEach(x=>{const o=document.createElement('option');o.value=x;o.textContent=x;sel.appendChild(o);});
});
async function make(){
  const t=document.getElementById('text').value.trim();
  if(!t){alert('先输入文字');return;}
  const btn=document.getElementById('go');btn.disabled=true;
  document.getElementById('tip').textContent='合成中，请稍等...';
  try{
    const r=await fetch('/api/tts?text='+encodeURIComponent(t)+'&voice='+encodeURIComponent(document.getElementById('voice').value));
    if(!r.ok) throw new Error(await r.text());
    const b=await r.blob();
    document.getElementById('player').src=URL.createObjectURL(b);
    document.getElementById('player').play();
    document.getElementById('tip').textContent='完成！右键播放器可另存为 mp3。';
  }catch(e){document.getElementById('tip').textContent='出错了：'+e.message;}
  btn.disabled=false;
}
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def index():
    return PAGE


@app.get("/api/voices")
async def voices():
    return POPULAR_VOICES


def _clean(text: str) -> str:
    text = (text or "").strip()
    if not text:
        raise HTTPException(400, "text 不能为空")
    if len(text) > 2000:
        raise HTTPException(400, "文字太长，单次最多 2000 字")
    return text


@app.get("/api/tts")
async def tts_get(
    text: str = Query(...),
    voice: str = Query(DEFAULT_VOICE),
    rate: str = Query("+0%", description="语速，如 +10% / -20%"),
):
    text = _clean(text)
    if voice not in POPULAR_VOICES:
        voice = DEFAULT_VOICE
    com = edge_tts.Communicate(text, voice=voice, rate=rate)
    buf = io.BytesIO()
    async for chunk in com.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])
    audio = buf.getvalue()
    if not audio:
        raise HTTPException(502, "合成失败，请稍后再试")
    return Response(content=audio, media_type="audio/mpeg",
                    headers={"Content-Disposition": 'inline; filename="tts.mp3"'})


@app.post("/api/tts")
async def tts_post(body: dict):
    text = _clean(body.get("text", ""))
    voice = body.get("voice") or DEFAULT_VOICE
    if voice not in POPULAR_VOICES:
        voice = DEFAULT_VOICE
    rate = body.get("rate", "+0%")
    com = edge_tts.Communicate(text, voice=voice, rate=rate)
    buf = io.BytesIO()
    async for chunk in com.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])
    audio = buf.getvalue()
    if not audio:
        raise HTTPException(502, "合成失败，请稍后再试")
    return Response(content=audio, media_type="audio/mpeg")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
