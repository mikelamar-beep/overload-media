# Captures app screenshots for Overload batch-2 videos from the Pro test build (localhost:8766), phone size @3x.
import asyncio, json, time, sys
from playwright.async_api import async_playwright
CH="/opt/pw-browsers/chromium-1243/chrome-linux64/chrome"; URL="http://localhost:8766/"
D=864e5; NOW=int(time.time()*1000)
def S(w,r,d=2): return {"w":w,"r":r,"d":d}
DAYS={  # bro split day -> list of (key, start weight, inc per week, reps, sets)
 "chest":[("bench",175,5,8,3),("incdb",60,5,10,3),("pecdeck",110,10,12,3),("pushdown",50,5,12,3)],
 "back":[("row",155,5,8,3),("pulldown",140,10,10,3),("dbrow",70,5,10,3),("ezcurl",60,5,10,3)],
 "shoulders":[("ohp",105,5,8,3),("clat",15,2.5,12,3),("rdfly",30,5,12,3),("bbshrug",185,10,12,3)],
 "legs":[("squat",225,10,6,3),("rdl",185,10,8,3),("legext",120,10,12,3),("scalf",160,10,12,3)],
 "arms":[("cgbench",145,5,8,3),("hammer",35,5,10,3),("ohext",50,5,12,3),("inccurl",25,5,10,3)],
}
ORDER=["chest","back","shoulders","legs","arms"]
def seed(weeks=4, stall=None, skip_recent_days=1):
    out=[]; i=0
    for wk in range(weeks):
        for j,day in enumerate(ORDER):
            ago=(weeks-1-wk)*7 + (len(ORDER)-j) + skip_recent_days - 1
            ex=[]
            for (k,w0,inc,r,n) in DAYS[day]:
                w=w0+inc*wk
                if stall==k and wk>=weeks-4: w=w0+inc*(weeks-4) if weeks>=4 else w0
                ex.append({"key":k,"sets":[S(w,r,3 if s==n-1 else 2) for s in range(n)]})
            out.append({"id":f"s{i}","ts":NOW-int(ago*D)-3600e3*6,"day":"heavy" if (wk+j)%2==0 else "volume","minutes":44,"model":46,"target":45,"exercises":ex}); i+=1
    return sorted(out,key=lambda s:-s["ts"])
async def text(pg): return await pg.evaluate("()=>document.body.innerText")
async def tap(pg, t, exact=True, nth=0):
    loc=pg.get_by_text(t, exact=exact); n=await loc.count()
    for k in range(n):
        el=loc.nth(k)
        if await el.is_visible():
            await el.click(); await pg.wait_for_timeout(450); return True
    return False
async def onboard(ctx, state_patch):
    pg=await ctx.new_page(); await pg.goto(URL, wait_until="networkidle"); await pg.wait_for_timeout(2500)
    for _ in range(16):
        body=await text(pg)
        for c in ["Build muscle","6 days","Bro split","Some experience","40–54","No thanks"]:
            if c in body: await tap(pg,c,exact=False)
        bts=await pg.evaluate("()=>[...document.querySelectorAll('[role=button],button')].filter(e=>e.offsetParent).map(e=>e.innerText.trim())")
        if "Build my first workout" in bts: await tap(pg,"Build my first workout"); break
        for c in ["Get started","Next","Looks good","Continue","Not now"]:
            if c in bts:
                try: await pg.get_by_text(c,exact=True).first.click(timeout=2500)
                except Exception: pass
                break
        await pg.wait_for_timeout(300)
    await pg.wait_for_timeout(600); await pg.close(); await asyncio.sleep(0.4)
    await ctx.add_init_script("""(()=>{ if (sessionStorage.getItem('seeded')) return; sessionStorage.setItem('seeded','1'); const k='overload-state-v1'; const s=JSON.parse(localStorage.getItem(k)); const p=%s; Object.assign(s, p.top||{}); s.settings=Object.assign(s.settings, p.settings||{}); s.editedAt=Date.now(); localStorage.setItem(k, JSON.stringify(s)); })()""" % json.dumps(state_patch))
    pg=await ctx.new_page(); await pg.goto(URL, wait_until="networkidle"); await pg.wait_for_timeout(3000)
    return pg
async def shot(pg, vid, n, full=False):
    import os; os.makedirs(f"/tmp/cap/{vid}",exist_ok=True)
    await pg.wait_for_timeout(350); await pg.screenshot(path=f"/tmp/cap/{vid}/{n:02d}.png", full_page=full)
async def build(pg, quick=None, groups_click=(), day=None, mins=None):
    if quick: await tap(pg, quick)
    for g in groups_click: await tap(pg, g)
    if day: await tap(pg, day)
    bt=[x for x in await pg.evaluate("()=>[...document.querySelectorAll('[role=button],button')].map(e=>e.innerText.trim())") if x.startswith("Build ") and "workout" in x]
    await pg.get_by_text(bt[0], exact=True).click(); await pg.wait_for_timeout(1400)
async def goto_ex(pg, name):
    for _ in range(8):
        b=await text(pg)
        if name in b.split("Exercise",1)[-1][:160]: return True
        nx=[x for x in await pg.evaluate("()=>[...document.querySelectorAll('[role=button],button')].map(e=>e.innerText.trim())") if x.startswith("Next") or (x.endswith("›") and ":" in x)]
        if not nx: return False
        await pg.get_by_text(nx[-1], exact=True).first.click(); await pg.wait_for_timeout(500)
    return False
async def log_rows(pg, upto=None, reps_last=None, weight=None):
    boxes=pg.locator('[aria-label^="Complete set"]'); n=await boxes.count(); upto=n if upto is None else upto
    for j in range(upto):
        row=boxes.nth(j).locator('xpath=..'); ins=row.locator('input')
        if weight and not await ins.nth(0).input_value(): await ins.nth(0).fill(str(weight))
        if reps_last and j==upto-1: await ins.nth(1).fill(str(reps_last))
        await boxes.nth(j).click(); await pg.wait_for_timeout(300)
    return n
BLOCK={"start":NOW-int(15*D),"anchors":{"chest":"bench","back":"row","shoulders":"ohp","quads":"squat","hamstrings":"rdl","triceps":"cgbench"}}
async def run(which):
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path=CH)
        async def ctxp(): return await b.new_context(viewport={"width":390,"height":844}, device_scale_factor=3)
        if "prshot" in which:
            ctx=await ctxp(); pg=await onboard(ctx,{"top":{"sessions":seed()},"settings":{"block":BLOCK}})
            await build(pg, quick="Push", day="Heavy day"); await goto_ex(pg,"Barbell Bench Press"); await shot(pg,"prshot",1)
            await tap(pg,"Use it for my next set"); await shot(pg,"prshot",2)
            await log_rows(pg, upto=4); await pg.wait_for_timeout(300)
            await tap(pg,"Skip"); await shot(pg,"prshot",3); await ctx.close()
        if "time" in which:
            ss=seed()
            for s in ss[:6]: s["minutes"]=40
            ctx=await ctxp(); pg=await onboard(ctx,{"top":{"sessions":ss},"settings":{"block":BLOCK}})
            await shot(pg,"time",1)
            await build(pg, quick="Push", day="Heavy day"); await shot(pg,"time",2)
            await ctx.close()
        if "block" in which:
            ctx=await ctxp(); pg=await onboard(ctx,{"top":{"sessions":seed()},"settings":{"block":BLOCK}})
            await shot(pg,"block",1)
            await build(pg, quick="Push", day="Heavy day"); await goto_ex(pg,"Barbell Bench Press"); await shot(pg,"block",2)
            ctx2=await ctxp(); pg2=await onboard(ctx2,{"top":{"sessions":seed()},"settings":{"block":dict(BLOCK,start=NOW-int(36*D))}}); await shot(pg2,"block",3)
            await ctx.close(); await ctx2.close()
        if "plateau" in which:
            ctx=await ctxp(); pg=await onboard(ctx,{"top":{"sessions":seed(stall="bench")},"settings":{"block":BLOCK}})
            await build(pg, quick="Push", day="Heavy day"); await goto_ex(pg,"Barbell Bench Press"); await shot(pg,"plateau",1)
            await tap(pg,"Reset to 90%"); await shot(pg,"plateau",2); await ctx.close()
        if "bonus" in which:
            ctx=await ctxp(); pg=await onboard(ctx,{"top":{"sessions":seed()},"settings":{"block":BLOCK}})
            await build(pg, quick="Push", day="Heavy day"); await goto_ex(pg,"Barbell Bench Press")
            n=await pg.locator('[aria-label^="Complete set"]').count()
            await log_rows(pg, upto=n-1); await tap(pg,"Skip")
            boxes=pg.locator('[aria-label^="Complete set"]'); ins=boxes.nth(n-1).locator('xpath=..').locator('input'); await ins.nth(1).fill("11")
            await shot(pg,"bonus",1)
            await boxes.nth(n-1).click(); await pg.wait_for_timeout(500); await tap(pg,"Skip"); await shot(pg,"bonus",2); await ctx.close()
        if "streak" in which:
            ctx=await ctxp(); pg=await onboard(ctx,{"top":{"sessions":seed(weeks=5, skip_recent_days=0)},"settings":{"block":BLOCK}})
            await shot(pg,"streak",1); await tap(pg,"Progress"); await pg.wait_for_timeout(600); await shot(pg,"streak",2); await ctx.close()
        if "growth" in which:
            ctx=await ctxp(); pg=await onboard(ctx,{"top":{"sessions":seed(weeks=6)},"settings":{"block":BLOCK}})
            await tap(pg,"Progress"); await pg.wait_for_timeout(600); await shot(pg,"growth",1); await ctx.close()
        if "recovery" in which:
            ctx=await ctxp(); pg=await onboard(ctx,{"top":{"sessions":seed(skip_recent_days=0)},"settings":{"block":BLOCK}})
            await pg.mouse.move(195,500); await pg.mouse.wheel(0,700); await pg.wait_for_timeout(700); await shot(pg,"recovery",1)
            await pg.mouse.wheel(0,-2000); await pg.wait_for_timeout(400)
            await build(pg, quick="Push", day="Heavy day")
            for _ in range(5):
                await log_rows(pg, weight=135)
                _t=await text(pg)
                nx=[x for x in await pg.evaluate("()=>[...document.querySelectorAll('[role=button],button')].map(e=>e.innerText.trim())") if x.startswith("Next") or (x.endswith("›") and ":" in x)]
                if not nx: break
                await pg.get_by_text(nx[-1],exact=True).first.click(); await pg.wait_for_timeout(500)
            fin=[x for x in await pg.evaluate("()=>[...document.querySelectorAll('[role=button],button')].map(e=>e.innerText.trim())") if "Finish" in x]
            if fin: await pg.get_by_text(fin[0],exact=True).first.click(); await pg.wait_for_timeout(1800)
            for k in range(3):
                if "ready again" in await text(pg): break
                await tap(pg,"Your week ›") or await tap(pg,"What's next ›"); await pg.wait_for_timeout(1000)
            await shot(pg,"recovery",2); await ctx.close()
        if "rest" in which:
            ctx=await ctxp(); pg=await onboard(ctx,{"top":{"sessions":seed()},"settings":{"block":BLOCK}})
            await build(pg, quick="Push", day="Heavy day"); await goto_ex(pg,"Barbell Bench Press")
            await log_rows(pg, upto=4); await pg.wait_for_timeout(1500); await shot(pg,"rest",1)
            await tap(pg,"Rest · tap to pause"); await pg.wait_for_timeout(300); await shot(pg,"rest",2); await ctx.close()
        if "remind" in which:
            ctx=await ctxp(); pg=await onboard(ctx,{"top":{"sessions":seed()},"settings":{"block":BLOCK,"reminders":{"on":True,"days":[2,3,4,5,6,7],"hour":18,"nudges":True}}})
            await pg.goto(URL+"onboarding?mode=remind", wait_until="networkidle"); await pg.wait_for_timeout(1500)
            await shot(pg,"remind",1); await ctx.close()
        await b.close()
asyncio.run(run(sys.argv[1:]))
