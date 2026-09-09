"""Exact source passages for audit references; no selection by question or answer."""
from copy import deepcopy
from .protocol import AUDIT_SCHEMA, HarnessError, obj, string

SPAN_SCHEMA = deepcopy(AUDIT_SCHEMA)
SPAN_SCHEMA['properties']['claims']['items']['properties']['quotes']['items'] = obj({'span_id': string(256)})


def source_span_packet(views, max_chars=1200):
    if not 100 <= max_chars <= 4000:
        raise ValueError('Audit span size must fit the ordinary quotation contract')
    observations, references = [], {}
    for view in views:
        passages=[]
        for part_index, part in enumerate(view['raw_parts']):
            start=0
            while start < len(part):
                end=min(start+max_chars,len(part))
                if end < len(part):
                    boundary=max(part.rfind('\n',start+max_chars//2,end),part.rfind(' ',start+max_chars//2,end))
                    if boundary >= 0:end=boundary+1
                span_id=f"{view['observation_id']}:{part_index}:{start}:{end}"
                if span_id in references:raise ValueError('Duplicate source span ID')
                quote=part[start:end]
                passages.append({'span_id':span_id,'text':quote})
                references[span_id]={'observation_id':view['observation_id'],'quote':quote,
                                     'raw_part_index':part_index,'start':start,'end':end}
                start=end
        observations.append({'observation_id':view['observation_id'],'docid':view['docid'],
                             'source_ranges':view.get('spans',[]),'passages':passages})
    return observations,references


def expand_references(report, references):
    """Call only after validating the wire schema. Unknown IDs never get corrected."""
    expanded=deepcopy(report)
    for row in expanded['claims']:
        quotes=[]
        for selected in row['quotes']:
            span_id=selected['span_id']
            if span_id not in references:
                raise HarnessError('audit_protocol_error',f'Unknown source span {span_id!r}; select an ID from the supplied passages')
            ref=references[span_id]
            quotes.append({'observation_id':ref['observation_id'],'quote':ref['quote']})
        row['quotes']=quotes
    return expanded
