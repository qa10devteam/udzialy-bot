# Inlines the traced BudOS logo paths into shorts.src.html -> shorts.html
import sys, pathlib
root = pathlib.Path(__file__).resolve().parent.parent
paths = dict(l.split('=', 1) for l in (root / 'brand' / 'budos-logo-paths.txt').read_text().strip().split('\n') if '=' in l and not l.startswith('W='))
s = (root / 'shorts.src.html').read_text()
for k in ('B', 'UD', 'OS'): s = s.replace(f'%%{k}%%', paths[k])
(root / 'shorts.html').write_text(s)
print('shorts.html', len(s))
