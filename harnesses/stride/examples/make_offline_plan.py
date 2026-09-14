"""Create a fully synthetic, label-free fixture plan. Does not access a model service."""
import argparse
from stride_search import Config
from stride_search.experiment import make_plan,write_new
from stride_search.fixtures import smoke_model,smoke_corpus
from stride_search.providers import ByteCounter

p=argparse.ArgumentParser()
p.add_argument('--output',required=True)
a=p.parse_args()
wrapper=make_plan([{'id':'synthetic-lumen','question':'Who was the first director of Lumen Observatory?'}],
    Config(max_model_calls=3),{'notes_off':{'notes_enabled':False},'notes_on':{}},
    model_identity=smoke_model().identity,retriever_identity=smoke_corpus().identity,
    counter_identity=ByteCounter.identity,seed=1)
write_new(a.output,wrapper)
print(wrapper['sha256'])
