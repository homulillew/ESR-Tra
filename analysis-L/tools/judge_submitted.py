"""用 OpenAICompatibleJudge 对 ESR 已提交答案做 LLM 语义复核。"""
import json, sys
sys.path.insert(0,'/data1/ESR-GRPO/ESR-GRPO/src')
from esr_grpo.browsecomp import load_examples
from esr_grpo.judge import OpenAICompatibleJudge

examples = {str(e.query_id): e for e in load_examples('/data1/ESR-GRPO/BrowseComp-Plus/data/prepared/browsecomp_plus_decrypted.jsonl')}
d = json.load(open('/data1/ESR-GRPO-Code/exp1_results/exp100_report.json'))
sub = [r for r in d['esr'] if r['submitted']]
judge = OpenAICompatibleJudge("http://127.0.0.1:8006/v1", "Qwen3.5-4B")
rows = []
for r in sub:
    qid = r['query_id']
    ex = examples[qid]
    j = judge.judge(ex.question, r['answer'], ex.answer)
    rows.append({"query_id": qid, "llm_correct": j.correct, "exact_correct": r["correct"],
                 "rationale": getattr(j, "rationale", "")})
    print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
n = sum(1 for x in rows if x["llm_correct"])
print(f"\n=== LLM judge: {n}/{len(rows)} = {100*n/len(rows):.1f}%", flush=True)
agree = sum(1 for x in rows if x["llm_correct"]==x["exact_correct"])
print(f"=== LLM 与 ExactMatch 一致 {agree}/{len(rows)}", flush=True)
json.dump(rows, open('/data1/ESR-GRPO-Code/analysis/esr_submitted_llm_judge.json','w'), ensure_ascii=False, indent=2)
