"""Look of the Campus YouBike Guide app: page styles, the logo lockup and the HTML for the cards.

Theme: NTUST blue (from the university seal) with YouBike orange as the accent.

Kept apart from streamlit_app.py so the app file reads as layout and logic only. Everything here
returns strings; nothing calls the model or the network.
"""
import html
import re

NAVY = "#005BAC"    # NTUST blue
INK = "#0E2A47"
ACCENT = "#FF9D19"  # YouBike orange
GREEN, ORANGE, RED, GREY = "#16A34A", "#F59E0B", "#DC2626", "#9CA3AF"

# Retrieval modes in the menu: key, name, what it does, median seconds per answer measured on the CPU
# laptop (eval/results/summary.md, 21-23 Nov 2026), icon. Hybrid v2 is the default.
MODES = [
    ("hybrid2", "Hybrid", "Graph route: place → gate → station, live YouBike, with reasons", 130, ":material/alt_route:"),
    ("local", "Local", "Entity-centred GraphRAG", 237, ":material/hub:"),
    ("global", "Global", "Community summaries, for overview questions", 388, ":material/public:"),
    ("drift", "DRIFT", "Iterative exploration, slow on a CPU", 1603, ":material/explore:"),
    ("basic", "Basic", "Traditional RAG, text chunks only", 93, ":material/description:"),
]
# The menu calls Hybrid v2 (graph route, eval key "hybrid2") just "Hybrid". The first Hybrid (Local
# search + nearest stations) is not in the menu: Hybrid v2 replaces it.
# It stays in the code and in the evaluation (eval/run_eval.py --modes hybrid).
HIDDEN = [("hybrid", "Hybrid v1", "Local search + nearest stations + live YouBike", 244, ":material/route:")]
MODE = {m[0]: m for m in MODES + HIDDEN}


def minutes(seconds):
    if seconds < 90:
        return f"about {round(seconds / 10) * 10:.0f} s"
    return f"about {max(1, round(seconds / 60)):.0f} min"


CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Source+Serif+4:opsz,wght@8..60,400;8..60,500;8..60,600&display=swap');
:root { --navy:#005BAC; --ink:#0E2A47; --side:#00427F; --accent:#FF9D19; --page:#F5F7FB; --line:#E1E7F0;
  --muted:#5F6B7D; --hero:#FFF4E3; --hero-line:#FFD49A; --soft:#EEF3F9; --lime:#B9BF0D; --green:#16A34A; --orange:#F59E0B;
  --red:#DC2626; --grey:#9CA3AF; --sans:"Inter","Segoe UI",system-ui,-apple-system,sans-serif;
  --display:"Source Serif 4","Tiempos Text",Georgia,"Times New Roman",serif; --mono:"JetBrains Mono",Consolas,monospace; }
.stApp, [data-testid="stAppViewContainer"] { background: var(--page); }
.stApp p, .stApp li, .stApp label, .stApp input, .stApp textarea, .stApp button { font-family: var(--sans); }
header[data-testid="stHeader"] { background: transparent; }
[data-testid="stMainBlockContainer"], .main .block-container { max-width: 1120px; padding-top: 2rem; padding-bottom: 4rem; }

/* ---------- sidebar ---------- */
section[data-testid="stSidebar"], section[data-testid="stSidebar"] > div {
  background: linear-gradient(180deg, #003B73 0%, #004C93 100%); }
section[data-testid="stSidebar"] p, section[data-testid="stSidebar"] span, section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] div { color: #E8F0FA; }
.yb-brand { display:flex; gap:14px; align-items:center; padding:4px 0 18px; border-bottom:1px solid rgba(255,255,255,.14); }
.yb-logo { width:48px; height:48px; border-radius:14px; background:linear-gradient(145deg, #FFB347 0%, #FF9D19 55%, #F28705 100%);
  display:grid; place-items:center; flex:none; box-shadow:0 6px 16px rgba(255,157,25,.35); }
.yb-brand b { display:block; font-family:var(--display); font-weight:600; font-size:21px; color:#fff; letter-spacing:-.01em; line-height:1.2; }
.yb-brand small { color:#B8CBE4; font-size:13px; }
.yb-side-label { font-size:11px; letter-spacing:.16em; text-transform:uppercase; color:#A9C3E3 !important;
  font-weight:700; margin:18px 0 6px; }
section[data-testid="stSidebar"] [data-testid="stSidebarContent"] { display:flex; flex-direction:column; }
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] { order:1; flex:1 0 auto; padding-top:2.2rem; }
section[data-testid="stSidebar"] [data-testid="stSidebarHeader"] { order:2; position:sticky; bottom:0; margin-top:auto;
  height:auto; min-height:0; padding:10px 18px 14px; justify-content:flex-start; background:#004C93;
  border-top:1px solid rgba(255,255,255,.14); z-index:2; }
section[data-testid="stSidebar"] [data-testid="stLogoSpacer"] { display:none; }
section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] { display:flex !important; visibility:visible !important; }
section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] button { color:#B8CBE4; border-radius:9px;
  padding:4px 8px; }
section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] button:hover { background:rgba(255,255,255,.08); }
section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] button::after { content:"Hide sidebar";
  font-size:12.5px; margin-left:6px; color:#B8CBE4; font-family:var(--sans); }
.yb-side-note { font-size:12px; line-height:1.5; color:#B8CBE4 !important; }
section[data-testid="stSidebar"] .stButton button { width:100%; background:rgba(255,255,255,.03);
  border:1px solid rgba(255,255,255,.14); border-radius:12px; padding:10px 12px; justify-content:flex-start;
  text-align:left; min-height:0; }
section[data-testid="stSidebar"] .stButton button p { font-size:13px; line-height:1.45; text-align:left; color:#E8F0FA; }
section[data-testid="stSidebar"] .stButton button:hover { border-color:var(--accent); background:rgba(255,157,25,.12); }
section[data-testid="stSidebar"] [data-baseweb="select"] > div { background:rgba(255,255,255,.06);
  border-color:rgba(255,255,255,.18); }
section[data-testid="stSidebar"] [data-baseweb="select"] svg { fill:#E8F0FA; }

/* ---------- page header ---------- */
.yb-crumb { font-size:11px; letter-spacing:.16em; text-transform:uppercase; color:var(--navy); font-weight:700;
  display:flex; align-items:center; gap:7px; margin-bottom:6px; }
.yb-title { font-family:var(--display); font-weight:500; font-size:36px; color:var(--ink); letter-spacing:-.02em;
  line-height:1.15; margin:0; }
.yb-sub { color:var(--muted); font-size:14.5px; margin:6px 0 0; }

/* Ask / Knowledge graph switch. Radio markup differs by Streamlit version: label[data-baseweb] up to
   about 1.45, label[data-testid=stRadioOption] later; both are styled. */
.st-key-viewbar [data-testid="stRadio"] { display:flex; justify-content:flex-end; width:100%; }
.st-key-viewbar [role="radiogroup"] { background:#fff; border:1px solid var(--line); border-radius:12px; padding:4px;
  gap:2px; display:inline-flex; flex-wrap:nowrap; box-shadow:0 1px 2px rgba(27,31,79,.05); }
.st-key-viewbar :is(label[data-baseweb="radio"], label[data-testid="stRadioOption"]) { padding:6px 12px; border-radius:9px;
  margin:0; cursor:pointer; }
.st-key-viewbar label[data-baseweb="radio"] > div:first-child,
.st-key-viewbar label[data-testid="stRadioOption"] > div > div:first-child:not([data-testid]) { display:none; }
.st-key-viewbar :is(label[data-baseweb="radio"], label[data-testid="stRadioOption"]) p { font-size:13.5px; font-weight:600;
  color:var(--ink); white-space:nowrap; }
.st-key-viewbar :is(label[data-baseweb="radio"], label[data-testid="stRadioOption"]):has(input:checked) { background:var(--navy); }
.st-key-viewbar :is(label[data-baseweb="radio"], label[data-testid="stRadioOption"]):has(input:checked) :is(p, span) { color:#fff; }

/* ---------- composer (question box with the mode menu, like a chat app) ---------- */
.st-key-composer { background:#fff; border:1px solid var(--line); border-radius:18px; padding:10px 12px 8px 14px;
  box-shadow:0 1px 2px rgba(27,31,79,.04), 0 10px 30px rgba(27,31,79,.06); gap:2px; }
.st-key-composer:focus-within { border-color:#B9CFEA; }
.st-key-composer [data-testid="stForm"] { border:none; padding:0; }
.st-key-composer { margin-top:14px; }
.st-key-composer [data-baseweb="input"], .st-key-composer [data-baseweb="base-input"],
.st-key-composer [data-testid="stTextInputRootElement"] { border:none; background:transparent; box-shadow:none; }
.st-key-composer [data-testid="stTextInput"] input { font-size:15.5px; color:var(--ink); padding-left:30px;
  background:transparent url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='18' height='18' viewBox='0 0 24 24' fill='none' stroke='%23005BAC' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z'/%3E%3C/svg%3E") no-repeat 4px center; }
.st-key-composer [data-testid="stFormSubmitButton"] button { background:var(--accent); border:none; color:var(--ink);
  border-radius:11px; font-weight:700; padding:6px 16px; min-height:38px; }
.st-key-composer [data-testid="stFormSubmitButton"] button p { font-weight:700; color:var(--ink); }
.st-key-composer [data-testid="stFormSubmitButton"] button:hover { background:#FFB04A; color:var(--ink); }
.st-key-modebar { gap:6px; }
/* mode menu and location menu side by side, 12 px apart; the hint takes the rest of the row */
.st-key-modebar [data-testid="stHorizontalBlock"] { gap:12px !important; flex-wrap:nowrap !important; }
.st-key-modebar :is([data-testid="stColumn"], [data-testid="column"]) { flex:0 0 auto !important; width:auto !important;
  min-width:0 !important; }
.st-key-modebar :is([data-testid="stColumn"], [data-testid="column"]):last-child { flex:1 1 auto !important; }
.st-key-modebar [data-testid="stPopover"] button { background:#fff; border:1px solid var(--line); border-radius:10px;
  padding:3px 10px; min-height:34px; color:var(--ink); white-space:nowrap; }
.st-key-modebar [data-testid="stPopover"] button p { font-weight:600; font-size:13.5px; color:var(--ink); }
.st-key-modebar [data-testid="stPopover"] button:hover { background:var(--soft); border-color:#B9CFEA; }
.st-key-loc_on [data-testid="stPopover"] button { background:#E8F1FB; border-color:#9CC3EA; }
.st-key-loc_on [data-testid="stPopover"] button :is(p, span) { color:#00467F; }
.st-key-geobox { position:absolute; width:0; height:0; overflow:hidden; }
.st-key-locmenu { padding:0 8px 4px; gap:8px; }
[data-testid="stPopoverBody"]:has(.st-key-locmenu) { width:400px !important; min-width:0; max-width:calc(100vw - 32px); }
.st-key-locmenu [data-testid="stButton"], .st-key-locmenu [data-testid="stButton"] button { width:100%; }
.st-key-locmenu [data-testid="stButton"] button { justify-content:flex-start; border-radius:10px; }
.yb-hint { color:var(--muted); font-size:12.5px; text-align:right; padding-top:6px; }
[data-testid="stPopoverBody"] { border-radius:14px; padding:8px 6px; min-width:340px; border:1px solid var(--line);
  box-shadow:0 12px 32px rgba(27,31,79,.14); }
.yb-menu-title { font-size:11px; letter-spacing:.14em; text-transform:uppercase; color:var(--muted); font-weight:700;
  padding:2px 10px 6px; }
[data-testid="stPopoverBody"] [role="radiogroup"] { gap:2px; }
[data-testid="stPopoverBody"] [data-testid="stRadio"], [data-testid="stPopoverBody"] [role="radiogroup"],
[data-testid="stPopoverBody"] [role="radiogroup"] > div { width:100%; }
[data-testid="stPopoverBody"] :is(label[data-baseweb="radio"], label[data-testid="stRadioOption"]) { display:flex; width:100%;
  padding:8px 10px; border-radius:10px; margin:0; align-items:flex-start; cursor:pointer; box-sizing:border-box; }
[data-testid="stPopoverBody"] :is(label[data-baseweb="radio"], label[data-testid="stRadioOption"]):hover { background:var(--soft); }
[data-testid="stPopoverBody"] label[data-baseweb="radio"] > div:first-child,
[data-testid="stPopoverBody"] label[data-testid="stRadioOption"] > div > div:first-child:not([data-testid]) { display:none; }
[data-testid="stPopoverBody"] :is(label[data-baseweb="radio"], label[data-testid="stRadioOption"]) p { color:var(--ink); }
[data-testid="stPopoverBody"] :is(label[data-baseweb="radio"], label[data-testid="stRadioOption"]):has(input:checked)::after {
  content:"\\2713"; margin-left:auto; color:var(--navy); font-weight:800; font-size:16px; padding-left:12px; }
.yb-menu-foot { color:var(--muted); font-size:11.5px; padding:6px 10px 2px; border-top:1px solid var(--line); margin-top:4px; }

/* ---------- cards ---------- */
.yb-card { background:#fff; border:1px solid var(--line); border-radius:20px; padding:20px 22px; }
.yb-label { font-size:11px; letter-spacing:.16em; text-transform:uppercase; color:var(--navy); font-weight:700;
  display:flex; align-items:center; gap:7px; }
.yb-pill { display:inline-block; background:var(--navy); color:#fff; font-size:11.5px; font-weight:700; border-radius:999px;
  padding:4px 11px; }
.st-key-hero { background:var(--hero); border:1px solid var(--hero-line); border-radius:22px; margin-top:6px;
  padding:0 18px 18px 0; gap:6px; overflow:hidden; }
.yb-hero-head { display:flex; justify-content:space-between; align-items:center; padding:14px 22px;
  border-bottom:1px solid var(--hero-line); margin-right:-18px; }
.yb-hero-left { padding:10px 0 0 24px; }
.st-key-hero [data-testid="stDeckGlJsonChart"] { border-radius:16px; overflow:hidden; border:1px solid #D5DEEA;
  margin-top:10px; background:#E8EEF5; box-shadow:0 1px 3px rgba(14,42,71,.08); }
.yb-maplegend { display:flex; gap:12px; flex-wrap:wrap; font-size:11.5px; color:var(--muted); padding:6px 2px 0; }
.yb-maplegend span { display:flex; align-items:center; gap:5px; }
.yb-kicker { font-size:11px; letter-spacing:.14em; text-transform:uppercase; color:#B5650A; font-weight:700;
  display:flex; gap:6px; align-items:center; }
.yb-station { font-family:var(--display); font-weight:600; font-size:32px; color:var(--ink); letter-spacing:-.02em;
  margin:6px 0 2px; line-height:1.1; }
.yb-zh { color:var(--muted); font-size:13px; }
.yb-dist { display:flex; align-items:center; gap:14px; margin:16px 0 10px; }
.yb-dist b { font-family:var(--display); font-size:44px; color:var(--navy); line-height:1; }
.yb-dist small { font-size:16px; color:var(--navy); font-weight:600; margin-left:2px; }
.yb-walk { border-left:1px solid var(--hero-line); padding-left:14px; color:var(--ink); font-size:13.5px; font-weight:600; }
.yb-addr { color:var(--muted); font-size:13px; margin-bottom:14px; }
.yb-stats { display:grid; grid-template-columns:1fr 1fr; gap:12px; max-width:420px; }
.yb-stat { background:#fff; border:1px solid var(--hero-line); border-radius:14px; padding:10px 14px; }
.yb-stat span { font-size:12px; color:var(--muted); display:flex; align-items:center; gap:6px; }
.yb-stat b { font-family:var(--display); font-size:30px; color:var(--ink); display:block; line-height:1.15; }
.yb-dot { width:8px; height:8px; border-radius:50%; display:inline-block; flex:none; }
.yb-actions { display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin-top:16px; }
.yb-btn { display:inline-flex; align-items:center; gap:6px; background:var(--navy); color:#fff !important;
  text-decoration:none !important; font-weight:700; font-size:13.5px; padding:9px 14px; border-radius:11px; }
.yb-btn.ghost { background:#fff; color:var(--navy) !important; border:1px solid var(--line); }
.yb-btn:hover { background:#004C93; }
.yb-btn.off { background:#C5D1DF; cursor:not-allowed; }
.yb-updated { color:var(--muted); font-size:12px; }
.yb-warn { margin-top:10px; font-size:12.5px; color:#8A4B00; }
.yb-section { display:flex; justify-content:space-between; align-items:flex-end; margin:26px 0 10px; }
.yb-section h3 { font-family:var(--display); font-size:21px; color:var(--ink); margin:0; padding:0; font-weight:600; }
.yb-section p { margin:2px 0 0; color:var(--muted); font-size:12.5px; }
.yb-grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(280px, 1fr)); gap:14px; }
.yb-other { background:#fff; border:1px solid var(--line); border-radius:18px; padding:16px 18px; }
.yb-other-head { display:flex; justify-content:space-between; gap:10px; }
.yb-other-head b { color:var(--ink); font-size:15px; }
.yb-chip-m { background:#E3EEF9; color:var(--navy); font-family:var(--mono); font-size:11.5px; border-radius:999px;
  padding:3px 9px; white-space:nowrap; height:fit-content; }
.yb-other .yb-stats { margin-top:12px; max-width:none; }
.yb-other .yb-stat { border:none; padding:0; background:none; }
.yb-bar { height:5px; background:var(--soft); border-radius:999px; margin:12px 0 8px; overflow:hidden; }
.yb-bar i { display:block; height:100%; border-radius:999px; }

/* place card and walking route */
.st-key-placecard { background:#fff; border:1px solid var(--line); border-radius:20px; padding:16px 20px; margin-top:14px; }
.st-key-placecard [data-testid="stImage"] img { border-radius:14px; }
.yb-kicker2 { font-size:11px; letter-spacing:.14em; text-transform:uppercase; color:var(--muted); font-weight:700; }
.yb-place-name { font-family:var(--display); font-weight:600; font-size:24px; color:var(--ink); margin:4px 0 2px;
  letter-spacing:-.01em; }
.yb-place .yb-actions { margin-top:10px; }
.yb-route { border-top:1px solid var(--line); margin-top:14px; padding-top:12px; }
.yb-steps { display:flex; flex-wrap:wrap; align-items:center; gap:6px 4px; margin:8px 0 2px; }
.yb-step { display:inline-flex; align-items:baseline; gap:5px; background:var(--soft); border:1px solid var(--line);
  border-radius:10px; padding:5px 10px; font-size:13px; color:var(--ink) !important; text-decoration:none !important; }
.yb-step small { color:var(--muted); font-size:11.5px; }
.yb-step i { font-style:normal; font-size:10.5px; font-weight:700; color:var(--navy); }
a.yb-step:hover { border-color:var(--navy); }
.yb-step.end { background:#FFF4E3; border-color:var(--hero-line); font-weight:600; }
.yb-arrow { color:var(--muted); font-size:13px; }

/* answer card */
.st-key-answer { background:#fff; border:1px solid var(--line); border-radius:20px; padding:20px 26px 16px; margin-top:22px; }
.st-key-answer [data-testid="stMarkdownContainer"] :is(p, li) { font-family:var(--display); font-size:17px; line-height:1.65;
  color:#1F2B3D; }
.yb-chips { display:flex; gap:8px; flex-wrap:wrap; }
.yb-chip { background:var(--soft); border:1px solid var(--line); color:var(--muted); font-size:12.5px; border-radius:999px;
  padding:4px 11px; }
.yb-chip b { color:var(--ink); font-weight:600; }
.yb-answer-title { font-family:var(--display); font-size:27px; font-weight:500; color:var(--ink); margin:12px 0 4px;
  letter-spacing:-.01em; }
.yb-cite { border-top:1px solid var(--line); padding-top:10px; font-family:var(--mono); font-size:12px; color:var(--navy);
  word-break:break-word; }
.yb-note { color:var(--muted); font-size:12.5px; }

/* expanders */
[data-testid="stExpander"] details { background:#fff; border:1px solid var(--line); border-radius:16px; }
[data-testid="stExpander"] summary { padding:14px 18px; }
[data-testid="stExpander"] summary p { font-weight:600; color:var(--ink); font-size:15px; }
.yb-src { background:var(--soft); border-radius:12px; padding:12px 14px; margin-bottom:10px; }
.yb-src small { font-size:10.5px; letter-spacing:.14em; text-transform:uppercase; color:var(--muted); font-weight:700; }
.yb-src b { display:block; color:var(--ink); font-size:14px; margin:3px 0; }
.yb-src p { color:#3B3F57; font-size:13px; margin:0; line-height:1.5; white-space:pre-wrap; }

/* empty state */
.yb-empty { background:#fff; border:1px dashed #CBD6E4; border-radius:20px; padding:26px; margin-top:18px; }
.yb-empty h4 { font-family:var(--display); color:var(--ink); font-size:20px; margin:0 0 4px; padding:0; }
.yb-empty p { color:var(--muted); font-size:14px; margin:0; }
.yb-kpis { display:grid; grid-template-columns:repeat(4, 1fr); gap:12px; margin-top:18px; }
.yb-kpi { background:var(--soft); border-radius:14px; padding:12px 14px; }
.yb-kpi b { font-family:var(--display); font-size:26px; color:var(--ink); display:block; }
.yb-kpi span { color:var(--muted); font-size:12.5px; }

@media (max-width: 900px) {
  .st-key-hero { padding-left:18px; }
  .yb-hero-left { padding-left:6px; }
  .yb-kpis { grid-template-columns:repeat(2, 1fr); }
}
</style>
"""

BIKE_SVG = ('<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#0E2A47" stroke-width="2.2" '
            'stroke-linecap="round" stroke-linejoin="round"><circle cx="5.5" cy="17.5" r="3.5"/>'
            '<circle cx="18.5" cy="17.5" r="3.5"/><circle cx="15" cy="5" r="1"/><path d="M12 17.5V14l-3-3 4-3 2 3h2"/></svg>')
TOUR_SVG = ('<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
            'stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/>'
            '<path d="M3 12c0-2.8 4-5 9-5s9 2.2 9 5-4 5-9 5"/><path d="m9 15 3 2-3 2"/></svg>')
SCHOOL_SVG = ('<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
              'stroke-linecap="round" stroke-linejoin="round"><path d="M22 10 12 5 2 10l10 5 10-5z"/>'
              '<path d="M6 12v5c3 2 9 2 12 0v-5"/></svg>')


def esc(text):
    return html.escape(str(text or ""))


def nice(name):
    """'NTUST(Main Gate)' -> 'NTUST (Main Gate)' for display."""
    return re.sub(r"(\S)\(", r"\1 (", str(name or ""))


def bike_color(bikes):
    if bikes is None:
        return GREY
    return RED if bikes == 0 else ORANGE if bikes < 3 else GREEN


def sidebar_brand():
    return (f'<div class="yb-brand"><div class="yb-logo">{BIKE_SVG}</div><div><b>YouBike Guide</b>'
            '<small>Taiwan Tech campus</small></div></div>'
            f'<div class="yb-side-label" style="display:flex;gap:7px;align-items:center">{SCHOOL_SVG}'
            'National Taiwan University of Science and Technology</div>')


def page_header():
    return (f'<div class="yb-crumb">{SCHOOL_SVG}Taiwan Tech <span style="opacity:.5">/</span> Campus mobility</div>'
            '<div class="yb-title">Campus YouBike Guide</div>'
            '<p class="yb-sub">Your nearest station, live availability and campus directions in one answer.</p>')


def empty_state(stats):
    kpis = "".join(f'<div class="yb-kpi"><b>{v}</b><span>{esc(k)}</span></div>' for k, v in stats)
    return ('<div class="yb-empty"><h4>Ask about getting around campus by YouBike</h4>'
            '<p>Pick a question on the left or type your own. Hybrid mode adds the nearest stations, '
            'live bike counts and a map, and explains the way from your place to the station. '
            'Everything runs on this laptop.</p>'
            f'<div class="yb-kpis">{kpis}</div></div>')


# ---------- station cards ----------

def _updated(text):
    """'2026-11-22 14:51:00' -> '14:51'."""
    m = re.search(r"(\d{1,2}:\d{2})", str(text or ""))
    return m.group(1) if m else ""


def _address(meta):
    addr = str(meta.get("aren") or meta.get("ar") or "").replace("，", ", ").replace(" ,", ",")
    near = meta.get("nearest_place")
    return " · ".join(x for x in [addr, f"near {near}" if near else ""] if x)


def hero_head(res):
    card = res["stations"][0]
    place = res.get("place")
    head = f"Nearest station to {place}" if place and card.get("distance_m") is not None else "Station in the answer"
    return (f'<div class="yb-hero-head"><div class="yb-label">◎ {esc(head)}</div>'
            '<span class="yb-pill">Closest</span></div>')


def tour_button(url):
    if url:
        return f'<a class="yb-btn" href="{esc(url)}" target="_blank" rel="noopener">{TOUR_SVG} 360° Tour ↗</a>'
    return (f'<span class="yb-btn off" title="Add this station\'s iStaging link to data/virtual_tours.csv">'
            f'{TOUR_SVG} 360° Tour · coming soon</span>')


def hero_left(res, meta_by_sno):
    """Left half of the nearest-station card; the map goes in the right half."""
    card = res["stations"][0]
    meta = meta_by_sno.get(card["sno"], {})
    dist = card.get("distance_m")
    dist_html = ""
    if dist is not None:
        walk = max(1, round(dist / 80))
        dist_html = (f'<div class="yb-dist"><b>{dist}<small>m</small></b><div class="yb-walk">About {walk} min walk'
                     '<br><span class="yb-updated">straight-line distance</span></div></div>')
    live = card.get("bikes") is not None
    bikes = card["bikes"] if live else "–"
    docks = card["free_docks"] if live else "–"
    stats = (f'<div class="yb-stats"><div class="yb-stat"><span><i class="yb-dot" style="background:{bike_color(card.get("bikes"))}">'
             f'</i>Bikes available</span><b>{bikes}</b></div><div class="yb-stat"><span>Free docks</span><b>{docks}</b>'
             '</div></div>')
    warn = ""
    if not live:
        warn = '<div class="yb-warn">Live counts are unavailable right now. Check the YouBike app before you go.</div>'
    elif card["bikes"] == 0:
        warn = '<div class="yb-warn">No bikes here right now. The stations below are the next closest.</div>'
    elif card.get("active") is False:
        warn = '<div class="yb-warn">This station is marked as not in service.</div>'
    actions = tour_button(card.get("tour_url"))
    if _updated(card.get("updated")):
        actions += f'<span class="yb-updated">Live data updated {_updated(card["updated"])}</span>'
    return (f'<div class="yb-hero-left"><div class="yb-kicker">➤ Closest by distance</div>'
            f'<div class="yb-station">{esc(nice(card["name"]))}</div>'
            f'<div class="yb-zh">{esc(card.get("name_zh"))} · Station {esc(card["sno"])}</div>'
            f'{dist_html}<div class="yb-addr">{esc(_address(meta))}</div>{stats}{warn}'
            f'<div class="yb-actions">{actions}</div></div>')


def map_legend():
    items = [("You asked", "#005BAC"), ("3+ bikes", GREEN), ("1–2 bikes", ORANGE), ("No bikes", RED),
             ("No live data", GREY), ("Other stations", "#FFC98A"), ("Campus buildings", "#B7C3D3")]
    return '<div class="yb-maplegend">' + "".join(
        f'<span><i class="yb-dot" style="background:{c}"></i>{t}</span>' for t, c in items) + "</div>"


def other_stations(cards):
    if not cards:
        return ""
    items = []
    for c in cards:
        live = c.get("bikes") is not None
        total = (c["bikes"] + c["free_docks"]) if live else 0
        fill = 100 * c["bikes"] / total if live and total else 0
        dist = f'<span class="yb-chip-m">{c["distance_m"]} m</span>' if c.get("distance_m") is not None else ""
        tour = (f' · <a href="{esc(c["tour_url"])}" target="_blank" rel="noopener">360° Tour ↗</a>'
                if c.get("tour_url") else "")
        items.append(
            f'<div class="yb-other"><div class="yb-other-head"><div><b>{esc(nice(c["name"]))}</b>'
            f'<div class="yb-zh">{esc(c.get("name_zh"))} · #{esc(c["sno"])}</div></div>{dist}</div>'
            f'<div class="yb-stats"><div class="yb-stat"><span><i class="yb-dot" style="background:{bike_color(c.get("bikes"))}">'
            f'</i>Bikes</span><b>{c["bikes"] if live else "–"}</b></div><div class="yb-stat"><span>Free docks</span>'
            f'<b>{c["free_docks"] if live else "–"}</b></div></div>'
            f'<div class="yb-bar"><i style="width:{fill:.0f}%;background:{bike_color(c.get("bikes"))}"></i></div>'
            f'<div class="yb-updated">{"Updated " + _updated(c.get("updated")) if _updated(c.get("updated")) else "No live data"}{tour}</div></div>')
    return ('<div class="yb-section"><div><h3>Other nearby stations</h3><p>Backup options if the main station is '
            'empty or full.</p></div><p>Sorted by distance</p></div>'
            f'<div class="yb-grid">{"".join(items)}</div>')


# ---------- answer ----------

CITE = re.compile(r"\s*\[Data:\s*((?:[^\[\]]|\[[^\]]*\])*)\]", re.I)
PART = re.compile(r"([A-Za-z][A-Za-z ]*?)?\s*\(([^()]*)\)")
BARE = re.compile(r"\s*\[(\d+(?:\s*[;,]\s*\d+)*)\]")  # inline '[66]' or '[99; 354]' outside a [Data: ...] block


def split_citations(answer):
    """Take GraphRAG's '[Data: Sources (33); Entities (2, 5)]' markers out of the text.

    Also accepts 'Facts (F1), (F2)' (the kind is carried over) and bare inline numbers such as
    '[66]', which are listed as 'Records'. Returns the clean text and one line such as
    'Reports (5) · Entities (2, 5) · Sources (33)'.
    """
    found = {}

    def keep(kind, ids):
        bucket = found.setdefault(kind, [])
        for i in (x.strip() for x in re.split(r"[,;]", ids)):
            if i and i not in bucket:
                bucket.append(i)

    for block in CITE.findall(answer or ""):
        kind = "Records"
        for k, ids in PART.findall(block):
            kind = k.strip().title() if k and k.strip() else kind
            keep(kind, ids)
    text = CITE.sub("", answer or "")
    for ids in BARE.findall(text):
        keep("Records", ids)
    text = BARE.sub("", text).strip()
    order = ["Facts", "Reports", "Entities", "Relationships", "Claims", "Sources", "Records"]
    kinds = sorted(found, key=lambda k: order.index(k) if k in order else 9)
    line = " · ".join(f"{k} ({', '.join(found[k][:12])}{', …' if len(found[k]) > 12 else ''})" for k in kinds)
    return text, line


def answer_chips(res):
    m = MODE.get(res["mode"])
    chips = [f'<span class="yb-chip">Mode <b>{esc(m[1] if m else res["mode"])}</b></span>',
             f'<span class="yb-chip"><b>{res["seconds"]:.0f} s</b> on this laptop</span>']
    if res.get("cached"):
        chips.append(f'<span class="yb-chip">Recorded answer <b>{esc(res["cached"])}</b></span>')
    if res.get("place"):
        chips.append(f'<span class="yb-chip">Place <b>{esc(res["place"])}</b></span>')
    return f'<div class="yb-chips">{"".join(chips)}</div>'


def place_card_html(card, kicker="Place in your question"):
    """Names of the place and its nearest 360° view."""
    sub = " · ".join(x for x in (card.get("name_zh"), card.get("code"),
                                 f"no. {card['map_no']} on the campus map" if card.get("map_no") else "") if x)
    pano = card.get("panorama")
    if pano and pano.get("url"):
        view = (f'<a class="yb-btn" href="{esc(pano["url"])}" target="_blank" rel="noopener">{TOUR_SVG} See it in 360° ↗</a>')
    elif pano:
        view = (f'<span class="yb-btn off" title="Add the panorama link to data/walkway_nodes.csv (tour_url)">'
                f'{TOUR_SVG} 360° view · coming soon</span>')
    else:
        view = ""
    note = (f'<div class="yb-updated" style="margin-top:8px">Nearest 360° view: {esc(pano["name"])}, about '
            f'{pano["metres"]} m away.</div>' if pano else
            '<div class="yb-updated" style="margin-top:8px">No 360° view near this place yet.</div>')
    return (f'<div class="yb-place"><div class="yb-kicker2">◎ {esc(kicker)}</div>'
            f'<div class="yb-place-name">{esc(card["name"])}</div><div class="yb-zh">{esc(sub)}</div>'
            + (f'<div class="yb-actions">{view}</div>' if view else "") + f'{note}</div>')


def route_html(walk, nodes):
    """The walking route as steps; each photographed step links to its 360° view when there is one."""
    head = (f'<div class="yb-kicker2">➜ Walking route · about {walk["metres"]} m · {walk["minutes"]} min</div>')
    if walk.get("direct"):
        why = ("The photographed paths do not go that way, so walk straight there."
               if walk.get("detour") else "Close enough to walk straight there.")
        body = (f'<div class="yb-steps"><span class="yb-step end">{esc(walk["origin"][:1].upper() + walk["origin"][1:])}</span><span class="yb-arrow">→</span>'
                f'<span class="yb-step end">{esc(walk["dest"])} <small>{walk["metres"]} m</small></span></div>'
                f'<div class="yb-updated">{why}</div>')
        return f'<div class="yb-route">{head}{body}</div>'
    steps = []
    last = len(walk["stops"]) - 1
    for i, (label, nid, m) in enumerate(walk["stops"]):
        label = label[:1].upper() + label[1:]
        url = (nodes.get(nid) or {}).get("tour_url", "") if nid else ""
        dist = f" <small>{m} m</small>" if i else ""
        tag = " <i>360°</i>" if nid else ""
        cls = "yb-step end" if i in (0, last) else "yb-step"
        if url:
            steps.append(f'<a class="{cls}" href="{esc(url)}" target="_blank" rel="noopener">{esc(label)}{tag}{dist}</a>')
        else:
            steps.append(f'<span class="{cls}" title="{esc(nid or "")}">{esc(label)}{tag}{dist}</span>')
    arrow = '<span class="yb-arrow">→</span>'
    body = f'<div class="yb-steps">{arrow.join(steps)}</div>'
    note = "Along the paths photographed for the 360° tour; steps marked 360° open that view once the tour is linked."
    if walk.get("off_route"):
        note += " " + " and ".join(walk["off_route"]) + " is off those paths, so that part is a straight-line estimate."
    return f'<div class="yb-route">{head}{body}<div class="yb-updated">{esc(note)}</div></div>'


def answer_title(res, text):
    if res["mode"] in ("hybrid", "hybrid2") and res.get("stations"):
        name = res["stations"][0]["name"]
        core = re.sub(r"[()]", " ", name).split()
        if name.lower() in text.lower() or (core and all(w.lower() in text.lower() for w in core)):
            return f"Why {nice(name)}?"
    if res.get("walk"):
        return "How to get there"
    return "Answer"


def sources_html(sources, limit=420):
    out = []
    for kind, title, text in sources:
        first, _, rest = text.partition("\n")
        if kind == "sources" and first.lower().startswith("source:"):
            title, text = first.split(":", 1)[1].strip(), rest.strip()
        label = {"sources": "Source", "reports": "Report", "entities": "Entity", "relationships": "Relationship",
                 "claims": "Claim", "facts": "Computed fact"}.get(kind, kind)
        body = text[:limit] + ("…" if len(text) > limit else "")
        out.append(f'<div class="yb-src"><small>{esc(label)}</small><b>{esc(title)}</b><p>{esc(body)}</p></div>')
    return "".join(out)
