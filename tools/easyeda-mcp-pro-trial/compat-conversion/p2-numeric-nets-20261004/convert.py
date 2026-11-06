#!/usr/bin/env python3
"""Narrow KiCad named-net compatibility experiment; no third-party dependencies."""
import argparse
import collections
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile
from dataclasses import dataclass

@dataclass
class Atom:
    raw: str
    start: int
    end: int

@dataclass
class Form:
    items: list
    start: int
    end: int

class Parser:
    """Recursive S-expression parser with quoted atoms and source spans."""
    def __init__(self, text):
        self.text, self.pos = text, 0

    def space(self):
        while self.pos < len(self.text) and self.text[self.pos].isspace():
            self.pos += 1

    def expression(self):
        self.space()
        start = self.pos
        if start >= len(self.text):
            raise ValueError('Unexpected end of input')
        char = self.text[self.pos]
        if char == '(':
            self.pos += 1
            items = []
            while True:
                self.space()
                if self.pos >= len(self.text):
                    raise ValueError('Unclosed form')
                if self.text[self.pos] == ')':
                    self.pos += 1
                    return Form(items, start, self.pos)
                items.append(self.expression())
        if char == ')':
            raise ValueError('Unexpected closing parenthesis')
        if char == '"':
            self.pos += 1
            while self.pos < len(self.text):
                char = self.text[self.pos]
                self.pos += 1
                if char == '\\':
                    if self.pos >= len(self.text):
                        raise ValueError('Unterminated escape')
                    self.pos += 1
                elif char == '"':
                    return Atom(self.text[start:self.pos], start, self.pos)
            raise ValueError('Unclosed quoted atom')
        while self.pos < len(self.text) and not self.text[self.pos].isspace() and self.text[self.pos] not in '()':
            self.pos += 1
        return Atom(self.text[start:self.pos], start, self.pos)

    def parse(self):
        root = self.expression()
        self.space()
        if self.pos != len(self.text):
            raise ValueError('Trailing expression')
        return root

def tag(node):
    return node.items[0].raw if isinstance(node, Form) and node.items and isinstance(node.items[0], Atom) else None

def forms(node, name):
    return [x for x in node.items if tag(x) == name]

def tree(node):
    return node.raw if isinstance(node, Atom) else [tree(x) for x in node.items]

def descend(node, parent=None):
    if isinstance(node, Form):
        yield node, parent
        for child in node.items:
            yield from descend(child, node)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    stem = 'kicad-integration-test'
    names = [stem + ext for ext in ('.kicad_pcb', '.kicad_sch', '.kicad_pro')]
    source = {name: (args.source/name).read_bytes() for name in names}
    pcb = source[names[0]].decode('utf-8')
    root = Parser(pcb).parse()
    assert tag(root) == 'kicad_pcb'
    assert not forms(root, 'net'), 'Already numbered or unexpected top-level nets'
    refs = [(node, parent) for node, parent in descend(root) if tag(node) == 'net']
    assert len(refs) == 18
    assert collections.Counter(tag(parent) for _, parent in refs) == {'pad':10, 'segment':8}
    for node, _ in refs:
        assert len(node.items) == 2 and isinstance(node.items[1], Atom) and node.items[1].raw.startswith('"')
    # Decode with JSON only after parsing the complete S-expression. For this
    # bounded sample, fail closed if a net uses a non-JSON string escape.
    raw_names = {node.items[1].raw for node, _ in refs}
    ordered = sorted(raw_names, key=json.loads)
    assert len(ordered) == 4 and all(json.loads(x) for x in ordered)
    mapping = {raw: i+1 for i, raw in enumerate(ordered)}
    changes = []
    for node, parent in refs:
        raw = node.items[1].raw
        suffix = ' ' + raw if tag(parent) == 'pad' else ''
        changes.append((node.start, node.end, f'(net {mapping[raw]}{suffix})'))
    table = '\n\t(net 0 "")' + ''.join(f'\n\t(net {mapping[raw]} {raw})' for raw in ordered)
    anchor = forms(root, 'setup')[0].end
    changes.append((anchor, anchor, table))
    converted = pcb
    for start, end, replacement in sorted(changes, reverse=True):
        converted = converted[:start] + replacement + converted[end:]
    result = Parser(converted).parse()
    lookup = {n.items[1].raw:n.items[2].raw for n in forms(result,'net')}
    assert lookup == {'0':'""', **{str(v):k for k,v in mapping.items()}}
    def normalize(node, is_root=False):
        if isinstance(node, Atom): return node.raw
        if tag(node) == 'net':
            number = node.items[1].raw
            assert number in lookup
            if len(node.items) == 3: assert node.items[2].raw == lookup[number]
            return ['net', lookup[number]]
        return [normalize(x) for x in node.items if not (is_root and tag(x) == 'net')]
    assert normalize(result, True) == tree(root), 'Non-net AST or net meaning changed'
    # Undo each change using parsed spans; require byte-for-byte source recovery.
    restore = []
    for n, parent in descend(result):
        if tag(n) != 'net': continue
        if parent is result: continue
        restore.append((n.start,n.end,'(net '+lookup[n.items[1].raw]+')'))
    restored = converted
    for start,end,replacement in sorted(restore,reverse=True):
        restored = restored[:start]+replacement+restored[end:]
    restored = restored[:anchor]+restored[anchor+len(table):]
    assert restored.encode() == source[names[0]], 'Non-net bytes changed'
    segments = forms(root,'segment')
    footprints = forms(root,'footprint')
    assert len(segments) == 8 and len(footprints) == 4
    def net_name(node): return json.loads(forms(node,'net')[0].items[1].raw)
    def vals(node, key): return tree(forms(node,key)[0])[1:]
    pad_records=[]
    for fp in footprints:
        reference = next(json.loads(p.items[2].raw) for p in forms(fp,'property') if p.items[1].raw=='"Reference"')
        for pad in forms(fp,'pad'):
            pad_records.append({'reference':reference,'pad':json.loads(pad.items[1].raw),'uuid':vals(pad,'uuid')[0], 'net':net_name(pad), 'numericId':mapping[forms(pad,'net')[0].items[1].raw], 'at':vals(pad,'at')})
    report = {
        'checkedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'purpose':'EasyEDA numeric-net compatibility experiment, not a full format downgrade',
        'sourceDirectory':str(args.source),'outputDirectory':str(args.output),
        'netMapping':{json.loads(k):v for k,v in mapping.items()},
        'baseline':{'topLevelNetTableEntries':0,'namedReferences':18,'numericLookupResolvableReferences':0},
        'checks':{'fullAstEqualAfterNetNormalization':True,'sourceBytesRecoveredAfterUndoingNetEdits':True,'versionUnchanged':True,'generatorVersionUnchanged':True,'layersUnchanged':True,'footprintsUnchangedExceptNetSyntax':True,'padNetMeaningsPreserved':True,'segmentGeometryWidthsLayersPreserved':True,'referenceCount':18,'padReferences':10,'segmentReferences':8,'footprints':4},
        'version':vals(root,'version')[0],'generatorVersion':json.loads(vals(root,'generator_version')[0]),
        'thickness':vals(forms(root,'general')[0],'thickness')[0],
        'stackupPresent':bool(forms(forms(root,'setup')[0],'stackup')),
        'pads':pad_records,
        'segments':[{'net':net_name(s),'numericId':mapping[forms(s,'net')[0].items[1].raw], **{key:vals(s,key) for key in ['start','end','width','layer','uuid']}} for s in segments],
    }
    # New output only; no overwrites and no source writes.
    args.output.mkdir(parents=True, exist_ok=False)
    package=args.output/'import-source';package.mkdir()
    for name,data in source.items():
        (package/name).write_bytes(converted.encode() if name.endswith('.kicad_pcb') else data)
    (args.output/'convert.py').write_bytes(Path(__file__).read_bytes())
    cli='/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'
    command=[cli,'pcb','export','stats','--format','json','--output',str(args.output/'kicad-stats.json'),str(package/names[0])]
    run=subprocess.run(command,capture_output=True,text=True,timeout=30)
    report['officialParserCheck']={'cli':cli,'command':command,'exitCode':run.returncode,'stdout':run.stdout,'stderr':run.stderr,'passed':run.returncode==0}
    report['sourceIntegrity']=[{'file':n,'sha256Before':sha(data),'sha256After':sha((args.source/n).read_bytes()),'unchanged':data==(args.source/n).read_bytes()} for n,data in source.items()]
    assert all(x['unchanged'] for x in report['sourceIntegrity'])
    report['copyHashes']={n:sha((package/n).read_bytes()) for n in names}
    archive=args.output/'Project2-Net-Compatibility.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for name in names:z.write(package/name,name)
    with zipfile.ZipFile(archive) as z:
        assert sorted(z.namelist()) == sorted(names)
        assert all(z.read(n)==(package/n).read_bytes() for n in names)
    report['zip']={'path':str(archive),'sha256':sha(archive.read_bytes()),'threeEntriesMatchCopies':True}
    (args.output/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['outputDirectory','netMapping','checks','officialParserCheck','sourceIntegrity','zip']},ensure_ascii=False,indent=2))

if __name__ == '__main__':main()
