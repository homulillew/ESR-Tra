"""Independent synthetic audit packets; expected labels stay in the evaluator."""

CASES = [
    ('quoting', 'Who founded the fictional Neral library? Return the name enclosed in literal double quotation marks.',
     'The fictional Neral library was founded by Aven Mor.', '"Aven Mor"', 'Aven Mor'),
    ('unit', 'What is the length of the fictional Luma bridge? Answer with the number followed by the unit m.',
     'The fictional Luma bridge is 37 meters long.', '37 m', '37'),
    ('ordering', 'List the fictional islands from earliest to latest discovery, using names separated by commas.',
     'Vela was discovered in 1810, Daro in 1790, and Fenn in 1840.', 'Daro, Vela, Fenn', 'Vela, Daro, Fenn'),
    ('count', 'Name exactly two fictional ports that opened before 1900, separated by commas.',
     'Pavo opened in 1870, Reni in 1880, Sola in 1920.', 'Pavo, Reni', 'Pavo'),
    ('target', 'Which fictional institution employed researcher Elan Su in 2031? Return only the institution name.',
     'In 2031 researcher Elan Su worked at the Tavi Institute.', 'Tavi Institute', 'Elan Su'),
    ('time', 'Who was director of the fictional Olan Museum in 2030? Return just the name.',
     'Nira Cole directed the Olan Museum from 2025 through 2032. Toma Sen became director in 2033.', 'Nira Cole', 'Toma Sen'),
]


def packets():
    for name, question, source, positive, negative in CASES:
        for compliant, answer in [(True, positive), (False, negative)]:
            # Findings state the source facts. They cannot replace the actual answer.
            state = {'target': question, 'answer': answer, 'claims': [
                {'claim_id': 'c0', 'requirement': question, 'finding': source, 'observation_ids': ['o1']}]}
            views = [{'observation_id': 'o1', 'docid': 'synthetic-' + name,
                      'text': source, 'raw_parts': [source], 'spans': [[0, len(source)]]}]
            yield {'name': name + ('-positive' if compliant else '-negative'), 'question': question,
                   'state': state, 'views': views, 'expected_supported': compliant}
