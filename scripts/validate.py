"""Validate catalog integrity and question payloads without executing reference code."""
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load(root, name):
    path = root / name
    assert not path.is_symlink() and path.resolve().is_relative_to(root.resolve()), f'Unsafe path: {name}'
    return json.loads(path.read_text())

def validate(root=ROOT):
    bank = load(root, 'bank.json')
    assert bank['schemaVersion'] == 1
    assert set(bank['entrypoints']) <= set(bank['catalogs'])
    catalogs = {key: load(root, path) for key, path in bank['catalogs'].items()}
    seen = set()
    def expand(key, visiting):
        assert key in catalogs and key not in visiting, f'Unknown or cyclic catalog: {key}'
        cat = catalogs[key]
        assert cat['id'] == key and cat['schemaVersion'] == 1
        result = []
        for chapter in cat['chapters']:
            assert chapter['name'] and isinstance(chapter['order'], int)
            for ident in chapter['questions']:
                assert ident in bank['questions'], f'Unknown question: {ident}'
                seen.add(ident)
                result.append(ident)
        for child in cat['includes']:
            result.extend(expand(child, visiting | {key}))
        assert len(result) == len(set(result)), f'Duplicate catalog entry: {key}'
        return result
    counts = {key: len(expand(key, set())) for key in catalogs}
    assert seen == set(bank['questions']), 'Unreferenced questions'
    paths = list(bank['questions'].values())
    assert len(paths) == len(set(paths)), 'Duplicate file mapping'
    actual = {str(p.relative_to(root)) for p in (root / 'questions').rglob('*.json')}
    assert actual == set(paths), 'Manifest/file mismatch'
    types, visibility = Counter(), Counter()
    for ident, path in bank['questions'].items():
        q = load(root, path)
        assert re.fullmatch(r'[a-z0-9][a-z0-9-]*', ident)
        assert q['id'] == ident and q['schemaVersion'] == 1 and q['revision'] >= 1
        assert q['subject'] in catalogs and q['chapter']
        task = q['task']
        assert q['visibility'] == 'public', f'Internal questions must stay in a private repository: {ident}'
        assert q['visibility'] == task['bankVisibility']
        assert task['category'] == 'problem' and task['title'] and task['description']
        assert task.get('fileIds', []) == [], f'External upload dependency: {ident}'
        assert not {'password', 'token', 'email', 'userId', 'createdBy'} & task.keys()
        origin = q['origin']
        if origin.get('type') == 'original':
            assert origin.get('author') and origin.get('description')
        else:
            assert origin['key'] == ident and re.fullmatch(r'[a-f0-9]{64}', origin['fileSha256'])
        assert all(url.startswith('https://') for url in q['sources'])
        visibility[q['visibility']] += 1
        if task['kind'] == 'code':
            judge = task['judge']
            assert judge['enabled'] and judge['languageIds'] and set(judge['languageIds']) <= {50, 54, 71}
            assert judge['timeLimitSeconds'] > 0
            cases = judge['testCases']
            assert cases and any(not c['hidden'] for c in cases) and any(c['hidden'] for c in cases)
            for case in cases:
                assert isinstance(case['input'], str) and isinstance(case['expectedOutput'], str)
                assert type(case['hidden']) is bool
            types['code'] += 1
        else:
            p = task['mechanicalProblem']; kind = p['type']; types[kind] += 1
            assert kind in ['single_choice', 'multiple_choice', 'fill_blank']
            assert p['answers'] and all(isinstance(a, str) and a for a in p['answers'])
            if kind != 'fill_blank':
                assert len(p['options']) >= 2
                assert all(a.isdigit() and 0 <= int(a) < len(p['options']) for a in p['answers'])
                assert len(p['answers']) == len(set(p['answers']))
                if kind == 'single_choice': assert len(p['answers']) == 1
    return {'uniqueQuestions': len(paths), 'catalogCounts': counts, 'types': dict(types), 'visibility': dict(visibility)}

if __name__ == '__main__':
    try:
        print(json.dumps(validate(Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT), ensure_ascii=False, indent=2))
    except (AssertionError, KeyError, ValueError, OSError) as error:
        sys.exit(f'Validation failed: {error}')
