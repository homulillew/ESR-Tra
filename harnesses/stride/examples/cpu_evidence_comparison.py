"""Offline mechanism comparisons on a NEW synthetic SQLite fixture, never a BC+ index."""
from __future__ import annotations
import argparse
from dataclasses import replace
import json
from pathlib import Path
import sqlite3

from stride_search import Config, Harness
from stride_search.contract import canonical
from stride_search.cpu_index import SQLiteFTS5
from stride_search.diagnostics import diagnose
from stride_search.experiment import write_new
from stride_search.fixtures import ScriptedModel, native
from stride_search.providers import ByteCounter


class GroupPressure(ByteCounter):
    identity = {'kind': 'synthetic_one_group_pressure', 'calibrated_provider_tokens': False}
    def __call__(self, wire):
        return 50000 * sum(m['role'] == 'assistant' for m in wire['messages']) + 100


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True)
    root = Path(p.parse_args().output); root.mkdir(parents=True,exist_ok=False)
    index = root/'SYNTHETIC_NOT_BCPLUS.sqlite'
    db = sqlite3.connect(index)
    db.executescript("CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT); CREATE TABLE docs(docid TEXT,content TEXT,url TEXT); CREATE VIRTUAL TABLE search USING fts5(content,content='docs',content_rowid='rowid',tokenize='porter unicode61');")
    db.execute('INSERT INTO metadata VALUES (?,?)',('identity',json.dumps({'complete':True,'documents':2})))
    db.executemany('INSERT INTO docs VALUES (?,?,?)',[
        ('a','Alpha venue-marker is led by Mira Stone.','https://fixture.test/alpha'),
        ('b','Beta is a different person.','https://fixture.test/beta')])
    db.execute("INSERT INTO search(search) VALUES ('rebuild')"); db.commit(); db.close()
    summary=[]
    for mechanism in ('cache','shelf'):
        for on in (False,True):
            cfg = Config(max_model_calls=6,recent_groups=1)
            if mechanism=='cache':
                cfg=replace(cfg,compiled_query_cache=on)
                replies=[native(('search',{'queries':['Mira Stone','"Mira Stone"']})),
                         native(('finish',{'abstain':True,'reason':'Navigation-only control'}))]
                counter=ByteCounter()
            else:
                cfg=replace(cfg,evidence_shelf_size=3 if on else 0)
                replies=[native(('search',{'queries':['Alpha']})),native(('read',{'ref':'d1'})),
                    native(('search',{'queries':['Beta']})),native(('read',{'ref':'d2'})),
                    native(('search',{'queries':['Beta again']})),
                    native(('finish',{'answer':'venue-marker','refs':['e1']}))]
                counter=GroupPressure()
            case=root/f'{mechanism}_{int(on)}'; case.mkdir()
            retriever=SQLiteFTS5(index,index_id='SYNTHETIC-NOT-BCPLUS')
            h=Harness('Identify the venue',retriever,path=case/'episode.sqlite',config=cfg,counter=counter)
            model=ScriptedModel(replies)
            try:
                h.run(model)
                write_new(case/'report.json',h.archive.report())
                write_new(case/'requests.json',model.requests)
                queries=[e['payload'] for e in h.archive.events() if e['kind']=='query_execution']
                summary.append({'mechanism':mechanism,'enabled':on,'outcome':h.terminal['outcome'],
                    'model_attempts':h.model_calls,'backend_attempts':h.backend_calls,
                    'queries':len(queries),'last_input_contains_marker':'venue-marker' in canonical(model.requests[-1]),
                    'actual_last_wire_bytes':len(canonical(model.requests[-1]).encode()),
                    'capacity_unit':counter.identity,'formal_correct':None})
            finally: h.close(); retriever.close()
            write_new(case/'diagnostic.json',diagnose(case/'episode.sqlite',include_text=True))
    output={'scope':'scripted synthetic comparisons, not live q26, not accuracy/efficiency estimates',
            'paid_model_calls':0,'rows':summary}
    write_new(root/'comparison.json',output)
    print(json.dumps(output,ensure_ascii=False,indent=2))


if __name__=='__main__': main()
