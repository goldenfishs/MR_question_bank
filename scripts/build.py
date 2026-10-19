"""Build a server sync artifact; student APIs must still filter answers."""
import hashlib
import json
from pathlib import Path
from validate import ROOT, load, validate

summary = validate()
bank = load(ROOT, 'bank.json')
questions = [load(ROOT, p) for _, p in sorted(bank['questions'].items())]
artifact = {'schemaVersion': 1, 'bank': bank['id'],
            'catalogs': {k: load(ROOT, p) for k, p in bank['catalogs'].items()},
            'questions': questions}
raw = (json.dumps(artifact, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()
out = ROOT / 'dist'; out.mkdir(exist_ok=True)
(out / 'bank.json').write_bytes(raw)
(out / 'bank.sha256').write_text(hashlib.sha256(raw).hexdigest() + '  bank.json\n')
print(json.dumps(summary, ensure_ascii=False))
print('Built dist/bank.json; contains publicly licensed answers and test cases.')
