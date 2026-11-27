"""PubChem SMILES -> RDKit SVG (기존 chem/*.svg와 같은 스타일). 사용: python render_chem.py [data/fda.json]"""
import json, os, re, sys
from rdkit import Chem
from rdkit.Chem.Draw import rdMolDraw2D

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PAL = {7: '#447AD8', 8: '#E0543D', 16: '#CC9E19', 9: '#3FA34C', 17: '#3FA34C', 35: '#3FA34C', 53: '#3FA34C', 15: '#CC9E19'}

def hex2rgb(h):
    h = h.lstrip('#'); return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))

def svg_for(smiles):
    m = Chem.MolFromSmiles(smiles)
    if m is None: return None
    w = max(360, 9 * m.GetNumHeavyAtoms()); h = round(w * 0.75)
    d = rdMolDraw2D.MolDraw2DSVG(w, h)
    o = d.drawOptions()
    o.clearBackground = False
    o.bondLineWidth = 1.6
    o.padding = 0.05
    o.setAtomPalette({-1: (0, 0, 0), 6: (0, 0, 0), 1: (0, 0, 0)})
    o.updateAtomPalette({k: hex2rgb(v) for k, v in PAL.items()})
    d.DrawMolecule(m); d.FinishDrawing()
    s = d.GetDrawingText()
    s = re.sub(r'<\?xml[^>]*\?>\s*', '', s)
    s = s.replace('#000000', 'currentColor')
    return s

def main(path):
    items = json.load(open(path))['items']
    os.makedirs(os.path.join(ROOT, 'chem'), exist_ok=True)
    made = 0
    for it in items:
        for c in it.get('chem') or []:
            fn = os.path.join(ROOT, 'chem', f"{c['cid']}.svg")
            if c.get('smiles') and not os.path.exists(fn):
                s = svg_for(c['smiles'])
                if s: open(fn, 'w').write(s); made += 1
    print('svg made', made)
    return made

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'data', 'fda.json'))
