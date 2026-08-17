#!/usr/bin/env node
/* napkin local server
 *
 * Exists for one reason: the API key should not live in the browser. The page
 * posts a description here, this process holds the key and talks to Anthropic,
 * and the browser never sees it.
 *
 *   node server/napkin.mjs        → http://localhost:8787
 *
 * The key comes from server/.env (ANTHROPIC_API_KEY=sk-ant-...) or the
 * environment. Both are gitignored / outside the repo. No dependencies.
 */

import {createServer} from "node:http";
import {readFile, writeFile} from "node:fs/promises";
import {readFileSync, existsSync} from "node:fs";
import {extname, join, resolve, normalize} from "node:path";
import {fileURLToPath} from "node:url";
import {schemaFor} from "./schema.mjs";

const HERE = resolve(fileURLToPath(import.meta.url), "..");
const DOCS = resolve(HERE, "..", "docs");
const STATE = join(HERE, "state.json");
const PORT = Number(process.env.PORT || 8787);

/* ---- key ---------------------------------------------------------------- */

function loadKey(){
  const f = join(HERE, ".env");
  if(existsSync(f)){
    for(const line of readFileSync(f, "utf8").split("\n")){
      const m = /^\s*([A-Z_]+)\s*=\s*(.*?)\s*$/.exec(line);
      if(m && !process.env[m[1]]) process.env[m[1]] = m[2].replace(/^["']|["']$/g, "");
    }
  }
  return (process.env.ANTHROPIC_API_KEY || "").trim();
}
const KEY = loadKey();

/* ---- models -------------------------------------------------------------
 * Prices are dollars per million tokens. Thinking tokens bill as output, so
 * cost stays accurate on models that think by default.                      */

const MODELS = [
  {id:"claude-haiku-4-5",  label:"Haiku 4.5",  in:1,  out:5,  note:"fastest, cheapest — plenty for routing"},
  {id:"claude-sonnet-5",   label:"Sonnet 5",   in:3,  out:15, note:"better at vague or unusual wording",
   introIn:2, introOut:10, introUntil:"2026-09-01"},
  {id:"claude-opus-5",     label:"Opus 5",     in:5,  out:25, note:"thinks by default — overkill here"},
];
const byId = id => MODELS.find(m => m.id === id);

function rates(m, when){
  const intro = m.introUntil && new Date(when) < new Date(m.introUntil);
  return intro ? {in:m.introIn, out:m.introOut} : {in:m.in, out:m.out};
}
function priceOf(modelId, usage, when){
  const m = byId(modelId); if(!m) return 0;
  const r = rates(m, when);
  const i = (usage?.input_tokens || 0) + (usage?.cache_read_input_tokens || 0)
          + (usage?.cache_creation_input_tokens || 0);
  const o = usage?.output_tokens || 0;
  return (i / 1e6) * r.in + (o / 1e6) * r.out;
}

/* ---- state --------------------------------------------------------------
 * Anthropic publishes no "remaining balance" endpoint — the Admin cost report
 * gives spend, not what's left. So the balance shown is whatever you tell it
 * you loaded, minus what napkin itself has spent. It cannot see spend from
 * Claude Code or anything else on the same account. Say so in the UI.        */

const EMPTY = {model:"claude-haiku-4-5", loaded:0, loadedAt:null, spent:0, calls:0, log:[]};
let state = {...EMPTY};

async function loadState(){
  try{ state = {...EMPTY, ...JSON.parse(await readFile(STATE, "utf8"))}; }
  catch(_){ /* first run */ }
  if(!byId(state.model)) state.model = EMPTY.model;
}
let saving = null;
function saveState(){
  // Coalesce writes; a burst of calls shouldn't mean a burst of fsyncs.
  if(saving) return saving;
  saving = new Promise(r => setTimeout(r, 50))
    .then(() => writeFile(STATE, JSON.stringify(state, null, 2)))
    .catch(() => {})
    .finally(() => { saving = null; });
  return saving;
}

const monthKey = ts => String(ts).slice(0, 7);
function summary(){
  const now = new Date().toISOString();
  const thisMonth = state.log.filter(c => monthKey(c.ts) === monthKey(now))
                              .reduce((a, c) => a + c.cost, 0);
  return {
    model: state.model,
    models: MODELS.map(m => ({...m, ...rates(m, now), intro: rates(m, now).in !== m.in})),
    spent: state.spent,
    calls: state.calls,
    month: thisMonth,
    loaded: state.loaded,
    loadedAt: state.loadedAt,
    left: state.loaded ? Math.max(0, state.loaded - state.spent) : null,
    last: state.log.length ? state.log[state.log.length - 1] : null,
  };
}

/* ---- the model call -----------------------------------------------------
 * The response schema has to stay inside Anthropic's strict-schema subset:
 * no union types (["string","null"]), and additionalProperties may only be
 * false — never a schema. That rules out a freeform {field: value} map, so
 * values come back as an array of records instead.                          */

const SYSTEM = `You route mechanical engineering sizing questions to a calculator and pre-fill what you can.

Calculators and their exact field keys:
{{CALCS}}

Rules:
- Pick the single best calculator. If genuinely unsure, say so in "unclear".
- Every "field" must be a field key listed for the calculator you picked. Never invent one.
- All values are US customary: inches, lbf, psi, F, BTU/hr, GPM, RPM, HP. Convert if the user writes metric.
- "value" is the number alone as a string ("8", "0.125"), or for a select field one of its listed options exactly.
- "predicted" is the most important thing you produce — an engineer will trust an unmarked value. Set it false only when the user actually stated the value (loosely counts: "about 8 inches" is stated). Set it true when you supplied it from typical practice or derived it from something else they said.
- Once you have picked a calculator, fill in every field. The engineer should land on a working starting point they can correct, not on empty boxes — an unfilled form is the least useful thing you can return. Every guess is marked and listed before it is used, so predicting is safe; staying silent is not.
- Predict from typical practice for the application described, and be concrete. Only leave a field out when there is genuinely no defensible starting value even loosely.
- If the user is asking you to size the thing itself (a wall thickness, a diameter), still put a plausible first value in it — that is what gets checked and iterated.
- Never predict 0 for a load, pressure, or dimension. A zero makes the result meaningless rather than approximate. Estimate a real magnitude from the application, or leave that field out entirely.
- "why" is required on predicted values: the actual reason an engineer would accept it ("typical wall for a 4 in vessel at this pressure"), not "commonly used". Use "" when predicted is false.
- "unclear" is one short sentence naming what you'd need to know, or "" if nothing is missing.`;

async function route({text, catalog, calculators}){
  const model = state.model;
  const res = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-api-key": KEY,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify({
      model,
      max_tokens: 1200,
      system: SYSTEM.replace("{{CALCS}}", catalog),
      messages: [{role: "user", content: text}],
      output_config: {format: {type: "json_schema", schema: schemaFor(calculators)}},
    }),
  });

  const body = await res.text();
  if(!res.ok){
    let detail = "";
    try{ detail = JSON.parse(body)?.error?.message || ""; }catch(_){}
    const err = new Error("anthropic"); err.status = res.status; err.detail = detail;
    throw err;
  }

  const data = JSON.parse(body);
  const ts = new Date().toISOString();
  const cost = priceOf(model, data.usage, ts);
  state.spent += cost;
  state.calls += 1;
  state.log.push({ts, model, cost,
    in: data.usage?.input_tokens || 0, out: data.usage?.output_tokens || 0});
  if(state.log.length > 500) state.log = state.log.slice(-500);
  saveState();

  const block = (data.content || []).find(b => b.type === "text");
  if(!block){ const e = new Error("empty"); e.status = 502; e.detail = "no text block came back"; throw e; }
  return {out: JSON.parse(block.text), cost, usage: data.usage, model};
}

/* ---- http --------------------------------------------------------------- */

const TYPES = {".html":"text/html; charset=utf-8", ".js":"text/javascript", ".css":"text/css",
  ".json":"application/json", ".svg":"image/svg+xml", ".png":"image/png", ".ico":"image/x-icon"};

const json = (res, code, obj) => {
  const b = JSON.stringify(obj);
  res.writeHead(code, {"content-type":"application/json", "content-length":Buffer.byteLength(b),
    "cache-control":"no-store"});
  res.end(b);
};

function readBody(req){
  return new Promise((ok, no) => {
    let n = 0; const parts = [];
    req.on("data", c => { n += c.length; if(n > 1e6){ no(new Error("too big")); req.destroy(); } parts.push(c); });
    req.on("end", () => { try{ ok(JSON.parse(Buffer.concat(parts).toString() || "{}")); }catch(e){ no(e); } });
    req.on("error", no);
  });
}

const server = createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);

  if(url.pathname === "/api/health")
    return json(res, 200, {ai: !!KEY, ...summary()});

  if(url.pathname === "/api/settings" && req.method === "POST"){
    let b; try{ b = await readBody(req); }catch(_){ return json(res, 400, {error:"bad body"}); }
    if(b.model){
      if(!byId(b.model)) return json(res, 400, {error:"unknown model"});
      state.model = b.model;
    }
    if(b.loaded !== undefined){
      const v = Number(b.loaded);
      if(!isFinite(v) || v < 0) return json(res, 400, {error:"bad amount"});
      state.loaded = v; state.loadedAt = new Date().toISOString();
      if(b.resetSpend){ state.spent = 0; state.calls = 0; state.log = []; }
    }
    await saveState();
    return json(res, 200, summary());
  }

  if(url.pathname === "/api/route" && req.method === "POST"){
    if(!KEY) return json(res, 503, {error:"No API key on the server. Put ANTHROPIC_API_KEY in server/.env and restart."});
    let b; try{ b = await readBody(req); }catch(_){ return json(res, 400, {error:"bad body"}); }
    if(!b.text || !b.catalog || !Array.isArray(b.calculators))
      return json(res, 400, {error:"need text, catalog and calculators"});
    try{
      const r = await route(b);
      return json(res, 200, {...r, spend: summary()});
    }catch(e){
      const status = e.status || 502;
      console.error(`  ai ${status}${e.detail ? " — " + e.detail : ""}`);
      return json(res, status, {error: e.detail || e.message, status});
    }
  }

  // static
  let p = url.pathname === "/" ? "/index.html" : url.pathname;
  const file = join(DOCS, normalize(p).replace(/^(\.\.[/\\])+/, ""));
  if(!file.startsWith(DOCS)) { res.writeHead(403); return res.end("no"); }
  try{
    const buf = await readFile(file);
    res.writeHead(200, {"content-type": TYPES[extname(file)] || "application/octet-stream",
      "cache-control":"no-store"});
    res.end(buf);
  }catch(_){ res.writeHead(404); res.end("not found"); }
});

await loadState();
server.listen(PORT, () => {
  console.log(`napkin  →  http://localhost:${PORT}`);
  console.log(KEY ? `  key loaded (…${KEY.slice(-6)}), model ${state.model}`
                  : `  no ANTHROPIC_API_KEY — rules-only, everything else works`);
  if(state.loaded) console.log(`  balance ${(state.loaded - state.spent).toFixed(4)} of ${state.loaded} left`);
});
