"""ID-only sampling and structural priors. Never uses labels for selection."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

SEED="esr-strong-api-20260909-v1"


def sha(value): return hashlib.sha256(value.encode()).hexdigest()


def prior(question):
    q=question.lower()
    counting=bool(re.search(r"\b(how many|total number|sum of|combined|excluding|except|neither)\b",q))
    temporal=len(re.findall(r"\b(before|after|between|earlier|later|same year|during)\b",q))
    bridge=len(re.findall(r"\b(whose|which was|who was|that was|where|both|same|named after|born|married|directed|founded)\b",q))
    if counting or temporal>=2 or bridge>=4:
        return "hard","Explicit counting/exclusion, multiple temporal constraints, or several entity relations; heuristic uncertainty high."
    if bridge>=2 or temporal>=1:
        return "medium","Explicit entity bridge or temporal relation; heuristic uncertainty high."
    return "easy","No multiple bridge/counting pattern detected; may still require substantial retrieval; heuristic uncertainty high."


def prepare(dataset, root, repo):
    root=Path(root)/"dataset_splits"; root.mkdir()
    questions={}
    with Path(dataset).open(encoding="utf-8") as f:
        for line in f:
            row=json.loads(line); qid=str(row["query_id"])
            if qid in questions: raise ValueError("Duplicate qid")
            questions[qid]=row["query"]
    # Detect historically executed IDs without extracting their answers or successful queries.
    excluded={"120","594","324","234","364","854","1000","170"}
    for folder in [Path(repo)/"move",Path(repo)/"results",Path(repo)/"analysis-L"]:
        for p in folder.rglob("*"):
            if p.is_file():
                excluded.update(re.findall(r"(?:^|[_\-.])q(\d+)(?:[_\-.]|$)",p.name))
    normalize=lambda q: " ".join(re.findall(r"\w+",q.lower()))
    shingles=lambda q: {tuple(q[i:i+4]) for i in range(max(1,len(q)-3))}
    historical=[shingles(normalize(questions[i]).split()) for i in excluded if i in questions]
    eligible=[]; signatures=[]; duplicates=[]
    for qid in sorted(questions,key=lambda i:sha(SEED+":"+i)):
        if qid in excluded: continue
        s=shingles(normalize(questions[qid]).split())
        if any(len(s&t)/max(1,len(s|t))>=0.8 for t in historical+signatures):
            duplicates.append(qid);continue
        eligible.append(qid);signatures.append(s)
    candidates=eligible[:24]
    strata={i:prior(questions[i]) for i in candidates}
    confirmation=[]
    for level in ["easy","medium","hard"]:
        confirmation.extend([i for i in candidates if strata[i][0]==level][:3])
    # Preserve imbalance rather than replace candidates using outcomes.
    confirmation += [i for i in candidates if i not in confirmation][:max(0,9-len(confirmation))]
    confirmation=confirmation[:9]
    pilot=[i for i in candidates if i not in confirmation]
    def save(name,ids):
        with (root/name).open("x",encoding="utf-8") as f:
            for qid in ids: f.write(json.dumps({"qid":qid,"question":questions[qid]},ensure_ascii=False)+"\n")
    save("known-regression.questions.jsonl",[i for i in ["120","594","324","234"] if i in questions])
    save("pilot.questions.jsonl",pilot)
    save("confirmation.questions.jsonl",confirmation)
    registry={"seed":SEED,"rule":"sha256(seed:qid); exclude known history and 4-word shingle Jaccard>=0.8; no outcomes or labels",
              "prior_rule":"explicit counting/exclusion, temporal constraints and relative entity relations; no word-count thresholds",
              "dataset_sha256":hashlib.sha256(Path(dataset).read_bytes()).hexdigest(),
              "excluded_historical_ids":sorted(excluded),"near_duplicates_excluded":duplicates,
              "candidates":[{"qid":i,"prior":strata[i][0],"reason":strata[i][1],"split":"confirmation" if i in confirmation else "pilot"} for i in candidates],
              "confirmation_hash":sha((root/"confirmation.questions.jsonl").read_text(encoding="utf-8")),
              "pilot_hash":sha((root/"pilot.questions.jsonl").read_text(encoding="utf-8")),
              "protection":"logical separate files; not OS access control; confirmation contents not printed or opened by development runner"}
    (root/"selection.json").write_text(json.dumps(registry,indent=2),encoding="utf-8")
    print(json.dumps({"eligible":len(eligible),"excluded_history":len(excluded),"candidates":len(candidates),
                      "confirmation_prior":dict(Counter(strata[i][0] for i in confirmation)),"pilot_prior":dict(Counter(strata[i][0] for i in pilot)),
                      "selection_sha256":sha(json.dumps(registry,sort_keys=True))}))


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--dataset",required=True);p.add_argument("--root",required=True)
    a=p.parse_args();prepare(a.dataset,a.root,Path(__file__).resolve().parents[1])
