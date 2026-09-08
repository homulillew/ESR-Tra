import json
from jsonschema import Draft202012Validator
from esr_harness.schema import export
from .helpers import env


def test_exported_schema_matches_contract_and_initial_state(tmp_path):
    export(tmp_path)
    for name in ['state.schema.json','actions.schema.json','audit.schema.json']:
        Draft202012Validator.check_schema(json.loads((tmp_path/name).read_text()))
    state=env().state
    Draft202012Validator(json.loads((tmp_path/'state.schema.json').read_text())).validate({k:v for k,v in state.items() if k!='research_version'})
    schema=Draft202012Validator(json.loads((tmp_path/'actions.schema.json').read_text()))
    schema.validate({'action':'update_state','arguments':{'answer':None}})
    assert list(schema.iter_errors({'action':'submit_answer','arguments':{'answer':'bypass'}}))
