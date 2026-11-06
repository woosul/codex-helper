"""Read-only KiCad snapshot analysis. No application/project settings are used."""
import hashlib, json, pathlib, re, sys

def parse(text):
    stack=[]; root=None
    for t in re.findall(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+',text):
        if t=='(':
            a=[]
            if stack: stack[-1].append(a)
            else: root=a
            stack.append(a)
        elif t==')': stack.pop()
        else:
            v=json.loads(t) if t.startswith('"') else t
            stack[-1].append(v)
    if stack: raise ValueError('unbalanced S-expression')
    return root
def children(n,key):return [x for x in n if isinstance(x,list) and x and x[0]==key]
def child(n,key,default=None):return next(iter(children(n,key)),default)
def props(n):return {x[1]:x[2] for x in children(n,'property')}
def xy(n,key):
    a=child(n,key)
    return [float(a[1]),float(a[2])] if a else None

root=pathlib.Path(sys.argv[1]); out=pathlib.Path(sys.argv[2])
stem='kicad-integration-test'
files={}
for ext in ['kicad_sch','kicad_pcb','kicad_pro']:
    p=root/(stem+'.'+ext);data=p.read_bytes()
    files[p.name]={'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'mtimeNs':p.stat().st_mtime_ns}
sch=parse((root/(stem+'.kicad_sch')).read_text())
pcb=parse((root/(stem+'.kicad_pcb')).read_text())
symbols=[]
for n in children(sch,'symbol'):
    p=props(n)
    symbols.append({'reference':p.get('Reference'),'value':p.get('Value'),'footprint':p.get('Footprint'),
      'libraryId':child(n,'lib_id',['lib_id',''])[1],'at':xy(n,'at'),'uuid':child(n,'uuid',['uuid',''])[1]})
fps=[]
for n in children(pcb,'footprint'):
    p=props(n)
    if not p:
      p={x[1].capitalize():x[2] for x in children(n,'fp_text') if x[1] in ['reference','value']}
    pads=[]
    for pad in children(n,'pad'):
      net=child(pad,'net')
      pads.append({'number':pad[1],'type':pad[2],'shape':pad[3],'net':net[-1] if net else '',
        'netId':int(net[1]) if net and len(net)>2 else None,'at':xy(pad,'at'),'size':xy(pad,'size')})
    fps.append({'reference':p.get('Reference'),'value':p.get('Value'),'footprint':n[1],
      'at':xy(n,'at'),'rotation':float(child(n,'at',['at','0','0','0'])[3]) if len(child(n,'at',[]))>3 else 0,
      'pads':pads,'models':children(n,'model')})
edges=[]
for n in pcb:
    if isinstance(n,list) and n and n[0].startswith('gr_') and child(n,'layer',['layer',''])[1]=='Edge.Cuts':
      e={'type':n[0]}
      for k in ['start','end','mid','center']:
        v=xy(n,k)
        if v:e[k]=v
      if child(n,'pts'):e['points']=[xy(x,'xy') if x and x[0]!='xy' else [float(x[1]),float(x[2])] for x in child(n,'pts')[1:]]
      edges.append(e)
nets=[{'id':int(n[1]),'name':n[2]} for n in children(pcb,'net')]
if not nets: nets=[{'id':None,'name':v} for v in sorted({p['net'] for f in fps for p in f['pads'] if p['net']})]
result={'files':files,'schematic':{'version':child(sch,'version')[1],'generatorVersion':child(sch,'generator_version')[1],
  'symbols':symbols,'electricalComponents':[s for s in symbols if s['reference'] and not s['reference'].startswith('#')]},
  'pcb':{'version':child(pcb,'version')[1],'footprints':fps,'nets':nets,'edgeCuts':edges,
    'segmentDetails':children(pcb,'segment'),'segments':len(children(pcb,'segment')),'arcs':len(children(pcb,'arc')),'vias':len(children(pcb,'via'))}}
out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'schematicVersion':result['schematic']['version'],'pcbVersion':result['pcb']['version'],
 'components':[(s['reference'],s['value']) for s in result['schematic']['electricalComponents']],
 'footprints':[(s['reference'],s['footprint'],len(s['pads'])) for s in fps],
 'nets':nets,'edgeCuts':edges,'segments':result['pcb']['segments']},ensure_ascii=False,indent=2))
