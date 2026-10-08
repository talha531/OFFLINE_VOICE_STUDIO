"""Audio player with real playback controls (play/pause/stop, seek, skip, speed, volume, loop).

The player is a small self-contained HTML document rendered in an iframe. The audio is embedded
as a data URI, so nothing is served from, or fetched over, the network. Very large files fall
back to Streamlit's built-in ``st.audio``.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from studio.audio.export import read_audio
from studio.audio.waveform import compute_peaks

MAX_EMBED_BYTES = 40 * 1024 * 1024
_MIME = {".wav": "audio/wav", ".mp3": "audio/mpeg", ".ogg": "audio/ogg", ".flac": "audio/flac"}

_TEMPLATE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root{color-scheme:dark;--s:#131720;--s2:#1b2130;--l:rgba(255,255,255,.1);--t:#e8eaf0;--m:#98a2b5;--a:#8b7cff}
*{box-sizing:border-box}
body{margin:0;font:14px/1.3 "Segoe UI Variable Text","Segoe UI",system-ui,sans-serif;color:var(--t);background:transparent}
.p{background:linear-gradient(180deg,#151a25,#111520);border:1px solid var(--l);border-radius:16px;padding:14px 16px}
canvas{width:100%;height:64px;display:block;cursor:pointer;border-radius:8px}
.r{display:flex;align-items:center;gap:8px;margin-top:10px;flex-wrap:wrap}
button,select{font:inherit;color:var(--t);background:var(--s2);border:1px solid var(--l);border-radius:10px;height:38px;min-width:38px;padding:0 10px;cursor:pointer;transition:background .15s,border-color .15s,transform .15s}
button:hover,select:hover{border-color:rgba(139,124,255,.6);background:#232a3b}
button:active{transform:scale(.96)}
button:focus-visible,select:focus-visible,input:focus-visible{outline:2px solid var(--a);outline-offset:2px}
#play{width:46px;height:46px;border-radius:50%;border:0;background:linear-gradient(135deg,#6f5cff,#b07cff);box-shadow:0 8px 20px -10px #7c6cff}
#play svg{width:20px;height:20px;fill:#fff;display:block;margin:auto}
button svg{width:16px;height:16px;stroke:currentColor;fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.t{font-variant-numeric:tabular-nums;color:var(--m);min-width:92px;font-size:13px}
.sp{flex:1}
label{display:flex;align-items:center;gap:6px;color:var(--m);font-size:12px}
input[type=range]{accent-color:var(--a);cursor:pointer}
#vol{width:84px}
#seek{width:100%;margin:8px 0 0;height:14px}
button[aria-pressed=true]{background:rgba(139,124,255,.22);border-color:rgba(139,124,255,.7);color:#fff}
.sr{position:absolute;left:-9999px}
@media(max-width:520px){#vol{width:60px}.t{min-width:80px}}
@media(prefers-reduced-motion:reduce){*{transition:none!important}}
</style></head><body>
<div class="p" role="group" aria-label="Audio player">
<canvas id="wf" aria-hidden="true"></canvas>
<input id="seek" type="range" min="0" max="1000" value="0" aria-label="Seek position">
<div class="r">
<button id="back" aria-label="Back 10 seconds" title="Back 10 s"><svg viewBox="0 0 24 24"><path d="M4 12a8 8 0 1 0 3-6.2L4 8M4 3v5h5"/></svg></button>
<button id="play" aria-label="Play" title="Play / pause"><svg viewBox="0 0 24 24" id="pi"><path d="M8 5v14l11-7z"/></svg></button>
<button id="stop" aria-label="Stop" title="Stop"><svg viewBox="0 0 24 24"><rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" stroke="none"/></svg></button>
<button id="fwd" aria-label="Forward 10 seconds" title="Forward 10 s"><svg viewBox="0 0 24 24"><path d="M20 12a8 8 0 1 1-3-6.2L20 8M20 3v5h-5"/></svg></button>
<span class="t" id="time" role="timer" aria-live="off">0:00 / 0:00</span><span class="sp"></span>
<label>Speed<select id="rate" aria-label="Playback speed"><option>0.75</option><option selected>1</option><option>1.25</option><option>1.5</option><option>2</option></select></label>
<label>Vol<input id="vol" type="range" min="0" max="100" value="100" aria-label="Volume"></label>
<button id="loop" aria-pressed="false" aria-label="Loop" title="Loop"><svg viewBox="0 0 24 24"><path d="M17 2l4 4-4 4M3 11V9a3 3 0 0 1 3-3h15M7 22l-4-4 4-4M21 13v2a3 3 0 0 1-3 3H3"/></svg></button>
</div>
<audio id="a" preload="metadata" src="__SRC__"></audio>
</div>
<script>
(function(){
var a=document.getElementById('a'),cv=document.getElementById('wf'),ctx=cv.getContext('2d');
var seek=document.getElementById('seek'),play=document.getElementById('play'),pi=document.getElementById('pi');
var time=document.getElementById('time'),peaks=__PEAKS__,dpr=window.devicePixelRatio||1,dragging=false;
var P='M8 5v14l11-7z',Q='M7 5h4v14H7zM13 5h4v14h-4z';
function f(s){s=isFinite(s)?s:0;var m=Math.floor(s/60),x=Math.floor(s%60);return m+':'+(x<10?'0':'')+x}
function draw(){
 var w=cv.clientWidth,h=cv.clientHeight;cv.width=w*dpr;cv.height=h*dpr;ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);
 var n=peaks.length||80,gap=2,bw=Math.max(2,(w-gap*(n-1))/n),prog=a.duration?a.currentTime/a.duration:0;
 for(var i=0;i<n;i++){var v=peaks.length?peaks[i]:.25,bh=Math.max(3,v*(h-6)),x=i*(bw+gap),y=(h-bh)/2;
  ctx.fillStyle=(i/n)<prog?'#8b7cff':'rgba(255,255,255,.2)';ctx.beginPath();
  if(ctx.roundRect){ctx.roundRect(x,y,bw,bh,Math.min(2,bw/2));}else{ctx.rect(x,y,bw,bh);}ctx.fill();}
}
function upd(){time.textContent=f(a.currentTime)+' / '+f(a.duration);if(!dragging&&a.duration){seek.value=Math.round(a.currentTime/a.duration*1000);}draw()}
function setIcon(){var on=!a.paused;pi.innerHTML='<path d="'+(on?Q:P)+'"/>';play.setAttribute('aria-label',on?'Pause':'Play')}
function toggle(){if(a.paused){a.play().catch(function(){})}else{a.pause()}}
play.onclick=toggle;
document.getElementById('stop').onclick=function(){a.pause();a.currentTime=0;upd()};
document.getElementById('back').onclick=function(){a.currentTime=Math.max(0,a.currentTime-10)};
document.getElementById('fwd').onclick=function(){a.currentTime=Math.min(a.duration||0,a.currentTime+10)};
document.getElementById('rate').onchange=function(e){a.playbackRate=parseFloat(e.target.value)};
document.getElementById('vol').oninput=function(e){a.volume=e.target.value/100};
var lp=document.getElementById('loop');lp.onclick=function(){a.loop=!a.loop;lp.setAttribute('aria-pressed',a.loop)};
seek.oninput=function(){dragging=true;if(a.duration){a.currentTime=seek.value/1000*a.duration}};
seek.onchange=function(){dragging=false};
cv.onclick=function(e){var r=cv.getBoundingClientRect();if(a.duration){a.currentTime=(e.clientX-r.left)/r.width*a.duration}};
a.addEventListener('timeupdate',upd);a.addEventListener('loadedmetadata',upd);a.addEventListener('play',setIcon);
a.addEventListener('pause',setIcon);a.addEventListener('ended',function(){setIcon();upd()});
document.body.addEventListener('keydown',function(e){if(e.code==='Space'&&e.target.tagName!=='BUTTON'&&e.target.tagName!=='SELECT'){e.preventDefault();toggle()}});
window.addEventListener('resize',draw);upd();setIcon();
})();
</script></body></html>"""


@st.cache_data(show_spinner=False, max_entries=48)
def _peaks_for(path: str, mtime: float) -> list[float] | None:
    try:
        return compute_peaks(read_audio(path).samples, 160)
    except Exception:  # unreadable or unsupported format: the player simply shows a plain bar
        return None


def audio_player(data: bytes, mime: str = "audio/wav", peaks: list[float] | None = None, height: int = 176) -> None:
    """Render ``data`` in the custom player (or ``st.audio`` if it is too large to embed)."""
    if len(data) > MAX_EMBED_BYTES:
        st.audio(data, format=mime)
        st.caption("Large file - using the basic player.")
        return
    src = f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"
    page = _TEMPLATE.replace("__SRC__", src).replace("__PEAKS__", json.dumps(peaks or []))
    components.html(page, height=height)


def file_player(path: str | Path, height: int = 176) -> bool:
    """Play a file from disk. Returns False (and shows nothing) if the file is missing."""
    path = Path(path)
    if not path.exists():
        return False
    mime = _MIME.get(path.suffix.lower(), "audio/wav")
    peaks = _peaks_for(str(path), path.stat().st_mtime) if path.stat().st_size < MAX_EMBED_BYTES else None
    audio_player(path.read_bytes(), mime, peaks, height)
    return True


def mime_for(filename: str) -> str:
    return _MIME.get(Path(filename).suffix.lower(), "audio/wav")


def bytes_player(data: bytes, mime: str = "audio/wav", height: int = 176) -> None:
    """Play in-memory audio (previews, uploaded or recorded references)."""
    try:
        peaks = compute_peaks(read_audio(data).samples, 160)
    except Exception:
        peaks = None
    audio_player(data, mime, peaks, height)
