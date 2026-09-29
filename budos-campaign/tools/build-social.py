# Builds social.html from social.src.html: inlines the logo paths, the QA10 mark and the pixel cursor.
import base64, pathlib, re
root = pathlib.Path(__file__).resolve().parent.parent
paths = dict(l.split('=', 1) for l in (root / 'brand' / 'budos-logo-paths.txt').read_text().strip().split('\n') if '=' in l and not l.startswith('W='))
qa10 = 'data:image/png;base64,' + base64.b64encode((root / 'brand' / 'qa10-by.png').read_bytes()).decode()
CURSOR = ('<svg class="cur" {attr} viewBox="0 0 12 19" shape-rendering="crispEdges" aria-hidden="true">'
          '<path d="M0 0v16h1v-1h1v-1h1v-1h1v2h1v2h1v2h2v-1h1v-2h-1v-2h-1v-2h3v-1h-1v-1h-1v-1h-1v-1h-1v-1h-1v-1h-1v-1h-1v-1h-1v-1h-1v-1z" fill="#000"/>'
          '<path d="M1 2v11h1v-1h1v-1h1v1h1v2h1v2h1v1h1v-2h-1v-2h-1v-2h3v-1h-1v-1h-1v-1h-1v-1h-1v-1h-1v-1h-1v-1h-1v-1z" fill="#fff"/></svg>')
s = (root / 'social.src.html').read_text()
for k in ('B', 'UD', 'OS'): s = s.replace(f'%%{k}%%', paths[k])
s = s.replace('%%QA10%%', qa10)
s = re.sub(r'%%CURSOR:(.*?)%%', lambda m: CURSOR.format(attr=m.group(1)), s)
assert '%%' not in s
(root / 'social.html').write_text(s)
print('social.html', len(s))
